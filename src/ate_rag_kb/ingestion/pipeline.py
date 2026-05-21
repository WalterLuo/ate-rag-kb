"""Markdown ingestion pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ate_rag_kb.chunking.models import Chunk
from ate_rag_kb.chunking.strategies import HierarchicalChunker
from ate_rag_kb.embedding.encoder import EmbeddingEncoder
from ate_rag_kb.utils.config import Config
from ate_rag_kb.vector_store.qdrant_client import QdrantVectorStore

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates markdown -> chunks -> embeddings -> vector store."""

    def __init__(
        self,
        config: Config,
        encoder: EmbeddingEncoder,
        vector_store: QdrantVectorStore,
        chunker: HierarchicalChunker | None = None,
        toc_tree: dict[str, Any] | None = None,
        href_map: dict[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.encoder = encoder
        self.vector_store = vector_store
        self.chunker = chunker or HierarchicalChunker(config)
        self._href_to_node = self._build_href_index(toc_tree)
        self._href_to_abs_path = self._build_abs_path_index(href_map)

    @staticmethod
    def _build_href_index(tree: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        """Build a flat href -> node_info index from nested toc_tree."""
        if not tree:
            return {}
        index: dict[str, dict[str, Any]] = {}

        def walk(node: dict[str, Any], parent_href: str | None = None) -> None:
            href = node.get("href", "")
            if href:
                index[href] = {
                    "label": node.get("label", ""),
                    "parent_href": parent_href,
                    "child_hrefs": [
                        c.get("href", "") for c in node.get("children", []) if c.get("href")
                    ],
                }
            for child in node.get("children", []):
                walk(child, href)

        walk(tree)
        return index

    @staticmethod
    def _build_abs_path_index(href_map: dict[str, Any] | None) -> dict[str, str]:
        """Build href -> absolute source path index from href_map."""
        if not href_map:
            return {}
        index: dict[str, str] = {}
        for abs_path, node in href_map.items():
            href = node.get("href", "")
            if href:
                index[href] = abs_path
        return index

    def _chunk_document(
        self,
        md_path: Path,
        json_path: Path | None = None,
        platform: str = "",
        doc_type: str = "",
    ) -> list[Chunk]:
        """Read and chunk a markdown document without embedding."""
        md_text = md_path.read_text(encoding="utf-8")

        metadata: dict[str, Any] = {}
        if json_path and json_path.exists():
            doc_meta = json.loads(json_path.read_text(encoding="utf-8"))
            # Flatten key fields from per-document JSON
            metadata["doc_title"] = doc_meta.get("title", "")
            metadata["toc_path"] = doc_meta.get("toc_path", [])
            metadata["source_html"] = doc_meta.get("source_html", "")
            metadata["images"] = doc_meta.get("images", [])
            # Merge remaining fields for downstream use
            for key, value in doc_meta.items():
                if key not in metadata:
                    metadata[key] = value

        source_md = str(md_path.relative_to(self.config.get("data.markdown_dir", ".")))
        source_json = str(json_path.relative_to(self.config.get("data.json_dir", "."))) if json_path else ""

        metadata["source_md"] = source_md
        metadata["source_json"] = source_json

        # Enrich with toc_tree parent/child relationships
        source_html = metadata.get("source_html", "")
        if source_html and self._href_to_node:
            node_info = self._href_to_node.get(source_html)
            if node_info:
                metadata["toc_parent_href"] = node_info.get("parent_href", "")
                metadata["toc_child_hrefs"] = node_info.get("child_hrefs", [])
                logger.debug(
                    "TOC enrichment for %s: parent=%s children=%d",
                    source_html,
                    node_info.get("parent_href"),
                    len(node_info.get("child_hrefs", [])),
                )

        # Source trace via href_map (available in metadata for API layer)
        if source_html and self._href_to_abs_path:
            abs_path = self._href_to_abs_path.get(source_html)
            if abs_path:
                metadata["source_html_path"] = abs_path

        chunks = self.chunker.chunk(
            text=md_text,
            metadata=metadata,
        )

        for chunk in chunks:
            if not chunk.platform:
                chunk.platform = platform
            if not chunk.doc_type:
                chunk.doc_type = doc_type

        return chunks

    def _embed_and_upsert(self, chunks: list[Chunk]) -> None:
        """Compute embeddings and upsert chunks into the vector store."""
        if not chunks:
            return
        try:
            texts = [c.content for c in chunks]
            embeddings = self.encoder.encode(texts)
            for chunk, emb in zip(chunks, embeddings):
                chunk.embedding = emb.tolist()
            self.vector_store.upsert_chunks(chunks)
        except RuntimeError as exc:
            message = str(exc).lower()
            is_memory_error = any(
                marker in message
                for marker in [
                    "invalid buffer size",
                    "out of memory",
                    "mps backend out of memory",
                ]
            )
            if not is_memory_error or len(chunks) == 1:
                raise

            midpoint = len(chunks) // 2
            logger.warning(
                "Embedding batch of %d chunks exceeded device memory; retrying as %d + %d.",
                len(chunks),
                midpoint,
                len(chunks) - midpoint,
            )
            self._embed_and_upsert(chunks[:midpoint])
            self._embed_and_upsert(chunks[midpoint:])

    def ingest_document(
        self,
        md_path: Path,
        json_path: Path | None = None,
        platform: str = "",
        doc_type: str = "",
    ) -> list[Chunk]:
        """Ingest a single markdown document."""
        chunks = self._chunk_document(md_path, json_path, platform, doc_type)
        self._embed_and_upsert(chunks)
        return chunks

    def ingest_directory(
        self,
        markdown_dir: Path,
        json_dir: Path | None = None,
        batch_size: int = 1000,
    ) -> int:
        """Batch ingest all markdown files in a directory with batched embedding."""
        md_files = sorted(markdown_dir.rglob("*.md"))
        logger.info("Found %d markdown files in %s", len(md_files), markdown_dir)

        total_chunks = 0
        batch_chunks: list[Chunk] = []

        for md_path in tqdm(md_files, desc="Ingesting"):
            json_path = None
            if json_dir:
                rel = md_path.relative_to(markdown_dir)
                json_path = json_dir / rel.with_suffix(".json")

            platform = self._detect_platform(md_path)
            doc_type = self._detect_doc_type(md_path)

            try:
                chunks = self._chunk_document(md_path, json_path, platform, doc_type)
            except Exception as exc:
                logger.error("Failed to chunk %s: %s", md_path, exc)
                continue

            batch_chunks.extend(chunks)

            if len(batch_chunks) >= batch_size:
                try:
                    self._embed_and_upsert(batch_chunks)
                    total_chunks += len(batch_chunks)
                except Exception as exc:
                    logger.error("Failed to embed batch containing %s: %s", md_path, exc)
                batch_chunks = []

        # Flush remaining chunks
        if batch_chunks:
            try:
                self._embed_and_upsert(batch_chunks)
                total_chunks += len(batch_chunks)
            except Exception as exc:
                logger.error("Failed to embed final batch: %s", exc)
            batch_chunks = []

        logger.info("Ingested %d chunks total.", total_chunks)
        return total_chunks

    @staticmethod
    def _detect_platform(path: Path) -> str:
        name = path.name.lower()
        if "j750" in name or "ultraflex" in name:
            return "J750"
        if "smt7" in name or "smt8" in name:
            return "SMT7"
        if "v93000" in name or "smartest" in name:
            return "V93000"
        if "tdc" in name:
            return "TDC"
        return ""

    @staticmethod
    def _detect_doc_type(path: Path) -> str:
        name = path.name.lower()
        if any(k in name for k in ["api", "reference", "command"]):
            return "api"
        if any(k in name for k in ["flow", "testflow"]):
            return "flow"
        if any(k in name for k in ["timing", "level", "pattern", "pin"]):
            return "hardware_config"
        if any(k in name for k in ["guide", "tutorial", "getting started"]):
            return "guide"
        return "reference"
