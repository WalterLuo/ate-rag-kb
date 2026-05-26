"""Cross-encoder reranker for retrieved chunks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sentence_transformers import CrossEncoder

from ate_rag_kb.chunking.models import Chunk
from ate_rag_kb.utils.config import Config

logger = logging.getLogger(__name__)


class Reranker:
    """Rerank query-chunk pairs using a cross-encoder."""

    def __init__(self, config: Config | None = None) -> None:
        cfg = config or Config({})
        self.model_name = cfg.get("retrieval.reranker.model_name", "BAAI/bge-reranker-v2-m3")
        self.top_k = cfg.get("retrieval.reranker.top_k", 5)
        self.batch_size = cfg.get("retrieval.reranker.batch_size", 16)
        self.cache_dir: Path = Path(cfg.get("embedding.cache_dir", "./embeddings/cache"))
        self.local_files_only: bool = cfg.get("embedding.local_files_only", True)
        self._model: CrossEncoder | None = None

    def _resolve_local_model_path(self) -> str:
        """Resolve a huggingface_hub cache entry to a local snapshot path."""
        if not self.local_files_only:
            return self.model_name

        safe_name = self.model_name.replace("/", "--")
        cache_entry = self.cache_dir / f"models--{safe_name}"
        snapshots_dir = cache_entry / "snapshots"

        if not snapshots_dir.exists():
            logger.warning(
                "No local cache found for %s at %s; falling back to model name",
                self.model_name,
                cache_entry,
            )
            return self.model_name

        for snapshot in snapshots_dir.iterdir():
            if snapshot.is_dir() and (snapshot / "config.json").exists():
                logger.info("Using local snapshot: %s", snapshot)
                return str(snapshot)

        logger.warning(
            "No valid snapshot found for %s; falling back to model name", self.model_name
        )
        return self.model_name

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            logger.info("Loading reranker: %s", self.model_name)
            model_path = self._resolve_local_model_path()
            self._model = CrossEncoder(
                model_path,
                local_files_only=self.local_files_only,
                cache_folder=str(self.cache_dir),
            )
        return self._model

    def rerank(self, query: str, chunks: list[Chunk], top_k: int | None = None) -> list[Chunk]:
        if not chunks:
            return []

        pairs = [(query, c.content) for c in chunks]
        scores = self.model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)

        scored = list(zip(chunks, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        tk = top_k or self.top_k
        return [c for c, _ in scored[:tk]]
