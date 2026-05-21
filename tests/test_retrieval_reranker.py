"""Unit tests for cross-encoder reranker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.retrieval.reranker import Reranker


class TestReranker:
    def test_rerank_returns_top_k(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            model = MagicMock()
            model.predict.return_value = [0.5, 0.9, 0.1]
            mock_cls.return_value = model

            reranker = Reranker()
            chunks = [
                Chunk(id="c1", content="low", chunk_type=ChunkType.PARAGRAPH),
                Chunk(id="c2", content="high", chunk_type=ChunkType.PARAGRAPH),
                Chunk(id="c3", content="lower", chunk_type=ChunkType.PARAGRAPH),
            ]

            result = reranker.rerank("query", chunks, top_k=2)

            assert len(result) == 2
            assert result[0].id == "c2"

    def test_rerank_empty_list(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder"):
            reranker = Reranker()

            result = reranker.rerank("query", [])

            assert result == []

    def test_rerank_uses_default_top_k(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            model = MagicMock()
            model.predict.return_value = [0.1] * 10
            mock_cls.return_value = model

            reranker = Reranker()
            reranker.top_k = 3
            chunks = [
                Chunk(id=f"c{i}", content=f"text{i}", chunk_type=ChunkType.PARAGRAPH)
                for i in range(10)
            ]

            result = reranker.rerank("query", chunks)

            assert len(result) == 3
