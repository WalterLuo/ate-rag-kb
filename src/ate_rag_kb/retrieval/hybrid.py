"""Hybrid retrieval: vector search + BM25 keyword search + fusion."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

from ate_rag_kb.chunking.models import Chunk
from ate_rag_kb.embedding.encoder import EmbeddingEncoder
from ate_rag_kb.utils.config import Config
from ate_rag_kb.vector_store.qdrant_client import QdrantVectorStore

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Combines dense vector search with sparse BM25 keyword search."""

    def __init__(
        self,
        encoder: EmbeddingEncoder,
        vector_store: QdrantVectorStore,
        config: Config | None = None,
    ) -> None:
        cfg = config or Config({})
        self.encoder = encoder
        self.vector_store = vector_store
        self.vector_top_k = cfg.get("retrieval.vector_search.top_k", 20)
        self.bm25_top_k = cfg.get("retrieval.bm25_search.top_k", 20)
        self.vector_weight = cfg.get("retrieval.hybrid.vector_weight", 0.7)
        self.bm25_weight = cfg.get("retrieval.hybrid.bm25_weight", 0.3)
        self.final_top_k = cfg.get("retrieval.hybrid.final_top_k", 10)
        self.k1 = cfg.get("retrieval.bm25_search.k1", 1.5)
        self.b = cfg.get("retrieval.bm25_search.b", 0.75)

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Retrieve chunks using hybrid fusion."""
        top_k = top_k or self.final_top_k

        query_vector = self.encoder.encode_query(query)
        vector_results = self.vector_store.search(
            query_vector.tolist(),
            top_k=self.vector_top_k,
            filters=filters,
        )

        bm25_results = self._bm25_search(query, vector_results)
        fused = self._reciprocal_rank_fusion(vector_results, bm25_results)
        return fused[:top_k]

    def _bm25_search(self, query: str, candidates: list[Chunk]) -> list[Chunk]:
        if not candidates:
            return []

        tokenized_corpus = [self._tokenize(c.content) for c in candidates]
        bm25 = BM25Okapi(tokenized_corpus, k1=self.k1, b=self.b)
        scores = bm25.get_scores(self._tokenize(query))

        scored = list(zip(candidates, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:self.bm25_top_k]]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return text.lower().split()

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[Chunk],
        bm25_results: list[Chunk],
    ) -> list[Chunk]:
        k = 60
        scores: dict[str, float] = {}

        for rank, chunk in enumerate(vector_results):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + self.vector_weight * (1.0 / (k + rank + 1))

        for rank, chunk in enumerate(bm25_results):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + self.bm25_weight * (1.0 / (k + rank + 1))

        id_to_chunk = {c.id: c for c in vector_results + bm25_results}
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [id_to_chunk[cid] for cid in sorted_ids if cid in id_to_chunk]
