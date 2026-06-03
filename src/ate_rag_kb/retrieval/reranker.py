"""Cross-encoder reranker for retrieved chunks."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sentence_transformers import CrossEncoder

from ate_rag_kb.chunking.models import Chunk
from ate_rag_kb.retrieval.chunk_quality import (
    chunk_quality_bonus,
    coverage_topic,
    is_low_utility_chunk,
)
from ate_rag_kb.utils.config import Config

logger = logging.getLogger(__name__)
_OFFLINE_ENV_VARS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")


class Reranker:
    """Rerank query-chunk pairs using a cross-encoder."""

    def __init__(self, config: Config | None = None) -> None:
        cfg = config or Config({})
        self.model_name = cfg.get("retrieval.reranker.model_name", "BAAI/bge-reranker-v2-m3")
        self.top_k = cfg.get("retrieval.reranker.top_k", 5)
        self.batch_size = cfg.get("retrieval.reranker.batch_size", 16)
        self.broad_candidate_top_k = cfg.get("retrieval.reranker.broad_candidate_top_k", 16)
        self.broad_final_top_k = cfg.get("retrieval.reranker.broad_final_top_k", 10)
        self.broad_max_sources = cfg.get("retrieval.reranker.broad_max_sources", 8)
        self.broad_min_sources = cfg.get("retrieval.reranker.broad_min_sources", 3)
        self.broad_max_chunks_per_source = cfg.get(
            "retrieval.reranker.broad_max_chunks_per_source", 3
        )
        requested_device = cfg.get("retrieval.reranker.device", "cpu")
        self.device: str = self._resolve_device(requested_device)
        self.cache_dir: Path = self._resolve_cache_dir(
            cfg.get("embedding.cache_dir", "./embeddings/cache")
        )
        self.local_files_only: bool = cfg.get("embedding.local_files_only", True)
        self._model: CrossEncoder | None = None
        self._last_rerank_stats: dict[str, int] = {}

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    @staticmethod
    def _resolve_cache_dir(cache_dir: str | Path) -> Path:
        path = Path(cache_dir).expanduser()
        if path.is_absolute():
            return path
        project_root = Path(__file__).resolve().parents[3]
        return project_root / path

    def _apply_network_mode(self) -> None:
        if self.local_files_only:
            for key in _OFFLINE_ENV_VARS:
                os.environ[key] = "1"
            os.environ.pop("HF_ENDPOINT", None)
            return

        for key in _OFFLINE_ENV_VARS:
            os.environ.pop(key, None)

    def _resolve_local_model_path(self) -> str:
        """Resolve a huggingface_hub cache entry to a local snapshot path."""
        if not self.local_files_only:
            return self.model_name

        safe_name = self.model_name.replace("/", "--")
        cache_entry = self.cache_dir / f"models--{safe_name}"
        snapshots_dir = cache_entry / "snapshots"

        if not snapshots_dir.exists():
            raise FileNotFoundError(
                f"Local model cache not found for {self.model_name} at {cache_entry}. "
                "Download the model with local_files_only=false, or unpack the offline "
                "model cache under embeddings/cache."
            )

        for snapshot in sorted(snapshots_dir.iterdir()):
            if snapshot.is_dir() and (snapshot / "config.json").exists():
                logger.info("Using local snapshot: %s", snapshot)
                return str(snapshot)

        raise FileNotFoundError(
            f"Local model cache not found for {self.model_name}: no valid snapshot with "
            f"config.json exists under {snapshots_dir}. Re-download or unpack the model cache."
        )

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            logger.info("Loading reranker: %s on %s", self.model_name, self.device)
            self._apply_network_mode()
            model_path = self._resolve_local_model_path()
            self._model = CrossEncoder(
                model_path,
                device=self.device,
                local_files_only=self.local_files_only,
                cache_folder=str(self.cache_dir),
            )
        return self._model

    def rerank(
        self,
        query: str,
        chunks: list[Chunk],
        top_k: int | None = None,
        is_broad_concept: bool = False,
    ) -> list[Chunk]:
        if not chunks:
            return []

        pairs = [(query, c.content) for c in chunks]
        scores = self.model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)

        scored = list(zip(chunks, scores, strict=True))
        scored.sort(key=lambda item: item[1], reverse=True)

        if is_broad_concept:
            scored.sort(
                key=lambda item: (
                    not is_low_utility_chunk(item[0]),
                    item[1] + chunk_quality_bonus(item[0]),
                ),
                reverse=True,
            )
            candidate_pool = scored[: self.broad_candidate_top_k]
            selected = self._select_coverage_diverse(
                [c for c, _ in candidate_pool],
                max_chunks=self.broad_final_top_k,
                max_sources=self.broad_max_sources,
                min_sources=self.broad_min_sources,
                max_chunks_per_source=self.broad_max_chunks_per_source,
            )
            self._last_rerank_stats = {
                "post_rerank_candidate_count": len(candidate_pool),
                "post_rerank_source_count": len(
                    {chunk.source_md for chunk, _ in candidate_pool if chunk.source_md}
                ),
                "post_diversity_candidate_count": len(selected),
                "post_diversity_source_count": len(
                    {chunk.source_md for chunk in selected if chunk.source_md}
                ),
                "low_utility_rerank_candidate_count": sum(
                    is_low_utility_chunk(chunk) for chunk, _ in candidate_pool
                ),
            }
            return selected

        tk = top_k or self.top_k
        selected = [c for c, _ in scored[:tk]]
        self._last_rerank_stats = {
            "post_rerank_candidate_count": len(selected),
            "post_rerank_source_count": len(
                {chunk.source_md for chunk in selected if chunk.source_md}
            ),
            "post_diversity_candidate_count": len(selected),
            "post_diversity_source_count": len(
                {chunk.source_md for chunk in selected if chunk.source_md}
            ),
            "low_utility_rerank_candidate_count": sum(
                is_low_utility_chunk(chunk) for chunk in selected
            ),
        }
        return selected

    @staticmethod
    def _select_coverage_diverse(
        chunks: list[Chunk],
        max_chunks: int,
        max_sources: int,
        min_sources: int,
        max_chunks_per_source: int,
    ) -> list[Chunk]:
        """Select content-bearing chunks with source and topic coverage.

        Pass 1: establish a small source-diverse base.
        Pass 2: add chunks that cover new sections or subtopics.
        Pass 3: fill remaining slots in rank order.
        """
        if not chunks:
            return []

        useful_chunks = [chunk for chunk in chunks if not is_low_utility_chunk(chunk)]
        candidates = useful_chunks or chunks
        result: list[Chunk] = []
        seen_sources: set[str] = set()
        seen_topics: set[tuple[str, str]] = set()
        seen_ids: set[str] = set()
        source_counts: dict[str, int] = {}

        def add(chunk: Chunk) -> bool:
            source = chunk.source_md or ""
            if chunk.id in seen_ids:
                return False
            if source not in seen_sources and len(seen_sources) >= max_sources:
                return False
            if source_counts.get(source, 0) >= max_chunks_per_source:
                return False
            result.append(chunk)
            seen_sources.add(source)
            seen_topics.add((source, coverage_topic(chunk).lower()))
            seen_ids.add(chunk.id)
            source_counts[source] = source_counts.get(source, 0) + 1
            return True

        for chunk in candidates:
            if len(result) >= max_chunks or len(seen_sources) >= min_sources:
                break
            if (chunk.source_md or "") not in seen_sources:
                add(chunk)

        for chunk in candidates:
            if len(result) >= max_chunks:
                break
            topic = (chunk.source_md or "", coverage_topic(chunk).lower())
            if topic not in seen_topics:
                add(chunk)

        for chunk in candidates:
            if len(result) >= max_chunks:
                break
            add(chunk)

        return result
