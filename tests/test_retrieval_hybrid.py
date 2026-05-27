"""Unit tests for hybrid retriever and RRF fusion."""

from __future__ import annotations

from unittest.mock import MagicMock

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.retrieval.hybrid import HybridRetriever


class TestHybridRetriever:
    def _make_encoder_and_store(self, vector_results: list[Chunk]) -> tuple:
        encoder = MagicMock()
        encoder.encode_query.return_value = MagicMock(tolist=lambda: [0.1] * 1024)

        store = MagicMock()
        store.search.return_value = vector_results

        return encoder, store

    def test_retrieve_returns_fused_results(self) -> None:
        chunks = [
            Chunk(id="c1", content="alpha", chunk_type=ChunkType.PARAGRAPH),
            Chunk(id="c2", content="beta", chunk_type=ChunkType.PARAGRAPH),
        ]
        encoder, store = self._make_encoder_and_store(chunks)

        retriever = HybridRetriever(encoder, store)
        result = retriever.retrieve("query", top_k=2)

        assert len(result) == 2
        assert {c.id for c in result} == {"c1", "c2"}

    def test_retrieve_respects_top_k(self) -> None:
        chunks = [
            Chunk(id=f"c{i}", content=f"text{i}", chunk_type=ChunkType.PARAGRAPH)
            for i in range(10)
        ]
        encoder, store = self._make_encoder_and_store(chunks)

        retriever = HybridRetriever(encoder, store)
        result = retriever.retrieve("query", top_k=3)

        assert len(result) == 3

    def test_retrieve_with_empty_candidates(self) -> None:
        encoder, store = self._make_encoder_and_store([])

        retriever = HybridRetriever(encoder, store)
        result = retriever.retrieve("query")

        assert result == []

    def test_reciprocal_rank_fusion_combines_scores(self) -> None:
        encoder, store = self._make_encoder_and_store([])
        retriever = HybridRetriever(encoder, store)

        v1 = Chunk(id="a", content="", chunk_type=ChunkType.PARAGRAPH)
        v2 = Chunk(id="b", content="", chunk_type=ChunkType.PARAGRAPH)
        b1 = Chunk(id="b", content="", chunk_type=ChunkType.PARAGRAPH)
        b2 = Chunk(id="c", content="", chunk_type=ChunkType.PARAGRAPH)

        fused = retriever._reciprocal_rank_fusion([v1, v2], [b1, b2])

        ids = [c.id for c in fused]
        assert "b" in ids  # appears in both lists
        assert len(ids) == 3

    def test_bm25_search_on_empty_returns_empty(self) -> None:
        encoder, store = self._make_encoder_and_store([])
        retriever = HybridRetriever(encoder, store)

        result = retriever._bm25_search("query", [])

        assert result == []

    def test_tokenize_splits_and_lowercases(self) -> None:
        result = HybridRetriever._tokenize("Hello World")

        assert result == ["hello", "world"]
