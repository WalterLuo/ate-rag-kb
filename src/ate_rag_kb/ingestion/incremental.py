"""Incremental ingestion with change detection."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ate_rag_kb.chunking.models import Chunk
from ate_rag_kb.ingestion.pipeline import IngestionPipeline
from ate_rag_kb.utils.config import Config

logger = logging.getLogger(__name__)

STATE_FILE = Path("./data/processed/ingestion_state.json")


class IncrementalIngestion:
    """Track file changes and only ingest new/modified documents."""

    def __init__(self, pipeline: IngestionPipeline, state_file: Path | None = None) -> None:
        self.pipeline = pipeline
        self.state_file = state_file or STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict[str, float]:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        return {}

    def _save_state(self, state: dict[str, float]) -> None:
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def scan_for_changes(
        self,
        markdown_dir: Path,
    ) -> tuple[list[Path], list[Path]]:
        """Return (new_files, modified_files)."""
        state = self._load_state()
        new_files: list[Path] = []
        modified_files: list[Path] = []

        for md_path in markdown_dir.rglob("*.md"):
            rel = str(md_path.relative_to(markdown_dir))
            mtime = md_path.stat().st_mtime
            if rel not in state:
                new_files.append(md_path)
            elif mtime > state[rel]:
                modified_files.append(md_path)

        return new_files, modified_files

    def run_incremental(
        self,
        markdown_dir: Path,
        json_dir: Path | None = None,
        batch_size: int = 1000,
    ) -> dict[str, int]:
        """Ingest only changed documents."""
        new_files, modified_files = self.scan_for_changes(markdown_dir)
        logger.info("Incremental scan: %d new, %d modified", len(new_files), len(modified_files))

        state = self._load_state()

        # Delete old chunks for modified files first
        for md_path in modified_files:
            rel = str(md_path.relative_to(markdown_dir))
            try:
                self.pipeline.vector_store.delete_by_source(rel)
                logger.info("Deleted old chunks for modified file: %s", rel)
            except Exception as exc:
                logger.error("Failed to delete old chunks for %s: %s", rel, exc)

        batch_chunks: list[Chunk] = []
        batch_rels: list[str] = []
        total_chunks = 0
        failed_count = 0
        successful_rels: list[str] = []

        # Helper to persist state immediately after a batch succeeds
        def _commit_batch(successful_batch_rels: list[str]) -> None:
            for r in successful_batch_rels:
                state[r] = (markdown_dir / r).stat().st_mtime
            self._save_state(state)

        for md_path in new_files + modified_files:
            rel = str(md_path.relative_to(markdown_dir))
            json_path = None
            if json_dir:
                json_path = json_dir / md_path.relative_to(markdown_dir).with_suffix(".json")

            platform = self.pipeline._detect_platform(md_path)
            doc_type = self.pipeline._detect_doc_type(md_path)

            # Step 1: chunk document (failure isolated to current file)
            try:
                chunks = self.pipeline._chunk_document(md_path, json_path, platform, doc_type)
            except Exception as exc:
                logger.error("Failed to chunk %s: %s", rel, exc)
                failed_count += 1
                continue

            batch_chunks.extend(chunks)
            batch_rels.append(rel)

            # Step 2: embed and upsert when batch is full (failure isolated to current batch)
            if len(batch_chunks) >= batch_size:
                try:
                    self.pipeline._embed_and_upsert(batch_chunks)
                    total_chunks += len(batch_chunks)
                    successful_rels.extend(batch_rels)
                    _commit_batch(batch_rels)
                except Exception as exc:
                    logger.error("Failed to embed batch ending at %s: %s", rel, exc)
                    failed_count += len(batch_rels)
                batch_chunks = []
                batch_rels = []

        # Flush remaining chunks
        if batch_chunks:
            try:
                self.pipeline._embed_and_upsert(batch_chunks)
                total_chunks += len(batch_chunks)
                successful_rels.extend(batch_rels)
                _commit_batch(batch_rels)
            except Exception as exc:
                logger.error("Failed to embed final batch: %s", exc)
                failed_count += len(batch_rels)
            batch_chunks = []
            batch_rels = []

        if total_chunks:
            logger.info(
                "Upserted %d chunks for %d changed files",
                total_chunks,
                len(successful_rels),
            )

        logger.info("Incremental ingestion complete.")
        return {
            "new": len(new_files),
            "modified": len(modified_files),
            "chunks": total_chunks,
            "failed": failed_count,
        }
