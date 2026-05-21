"""Unit tests for QdrantVectorStore."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.vector_store.qdrant_client import QdrantVectorStore


class TestQdrantVectorStore:
    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def store(self, mock_client: MagicMock) -> QdrantVectorStore:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls:
            qdrant_cls.return_value = mock_client
            with patch("ate_rag_kb.vector_store.qdrant_client.ensure_collection"):
                yield QdrantVectorStore()

    def test_upsert_chunks_skips_missing_embeddings(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        chunks = [
            Chunk(id="c1", content="text", chunk_type=ChunkType.PARAGRAPH, embedding=[0.1] * 1024),
            Chunk(id="c2", content="text2", chunk_type=ChunkType.PARAGRAPH, embedding=None),
        ]

        store.upsert_chunks(chunks)

        mock_client.upsert.assert_called_once()
        args = mock_client.upsert.call_args
        assert len(args.kwargs["points"]) == 1

    def test_search_returns_chunks_with_scores(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        mock_point = MagicMock()
        mock_point.id = "c1"
        mock_point.score = 0.95
        mock_point.payload = {"content": "hello", "chunk_type": "paragraph"}
        mock_client.search.return_value = [mock_point]

        result = store.search([0.1] * 1024, top_k=1)

        assert len(result) == 1
        assert result[0].id == "c1"
        assert result[0].score == 0.95

    def test_get_by_id_existing(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        mock_point = MagicMock()
        mock_point.id = "c1"
        mock_point.payload = {"content": "hello"}
        mock_client.retrieve.return_value = [mock_point]

        result = store.get_by_id("c1")

        assert result is not None
        assert result.id == "c1"

    def test_get_by_id_missing(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        mock_client.retrieve.return_value = []

        result = store.get_by_id("missing")

        assert result is None

    def test_delete_by_source(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        store.delete_by_source("doc.md")

        mock_client.delete.assert_called_once()

    def test_count(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        mock_client.count.return_value = MagicMock(count=42)

        result = store.count()

        assert result == 42

    def test_scroll_returns_chunks_and_offset(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        mock_point = MagicMock()
        mock_point.id = "c1"
        mock_point.payload = {"content": "hello"}
        mock_client.scroll.return_value = ([mock_point], "next_offset")

        chunks, offset = store.scroll(limit=1)

        assert len(chunks) == 1
        assert offset == "next_offset"
