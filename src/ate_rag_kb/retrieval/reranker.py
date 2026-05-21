"""Cross-encoder reranker for retrieved chunks."""

from __future__ import annotations

import logging
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
        self._model: CrossEncoder | None = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            logger.info("Loading reranker: %s", self.model_name)
            self._model = CrossEncoder(self.model_name)
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
