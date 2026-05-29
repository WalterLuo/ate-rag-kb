"""Unit tests for QdrantVectorStore."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.utils.config import Config
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

    def test_upsert_chunks_splits_large_requests_by_configured_batch_size(
        self,
        mock_client: MagicMock,
    ) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls:
            qdrant_cls.return_value = mock_client
            with patch("ate_rag_kb.vector_store.qdrant_client.ensure_collection"):
                store = QdrantVectorStore(Config({"vector_store": {"upsert_batch_size": 2}}))
        chunks = [
            Chunk(
                id=f"c{i}",
                content="large payload",
                chunk_type=ChunkType.PARAGRAPH,
                embedding=[0.1] * 1024,
            )
            for i in range(5)
        ]

        store.upsert_chunks(chunks)

        assert mock_client.upsert.call_count == 3
        batch_sizes = [len(call.kwargs["points"]) for call in mock_client.upsert.call_args_list]
        assert batch_sizes == [2, 2, 1]

    def test_search_returns_chunks_with_scores(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        mock_point = MagicMock()
        mock_point.id = "c1"
        mock_point.score = 0.95
        mock_point.payload = {"content": "hello", "chunk_type": "paragraph"}
        mock_response = MagicMock()
        mock_response.points = [mock_point]
        mock_client.query_points.return_value = mock_response

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

    def test_get_by_ids_batch_fetch(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        mock_p1 = MagicMock()
        mock_p1.id = "c1"
        mock_p1.payload = {"content": "hello"}
        mock_p2 = MagicMock()
        mock_p2.id = "c2"
        mock_p2.payload = {"content": "world"}
        mock_client.retrieve.return_value = [mock_p1, mock_p2]

        result = store.get_by_ids(["c1", "c2", "missing"])

        assert len(result) == 3
        assert result[0] is not None and result[0].id == "c1"
        assert result[1] is not None and result[1].id == "c2"
        assert result[2] is None
        mock_client.retrieve.assert_called_once()
        call_args = mock_client.retrieve.call_args
        assert call_args.kwargs["ids"] == ["c1", "c2", "missing"]

    def test_get_by_ids_empty_input(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        result = store.get_by_ids([])
        assert result == []
        mock_client.retrieve.assert_not_called()

    def test_get_by_ids_deduplicates(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        mock_p1 = MagicMock()
        mock_p1.id = "c1"
        mock_p1.payload = {"content": "hello"}
        mock_client.retrieve.return_value = [mock_p1]

        result = store.get_by_ids(["c1", "c1"])

        assert len(result) == 2
        assert result[0].id == "c1"
        assert result[1].id == "c1"
        call_args = mock_client.retrieve.call_args
        assert call_args.kwargs["ids"] == ["c1"]

    def test_scroll_returns_chunks_and_offset(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        mock_point = MagicMock()
        mock_point.id = "c1"
        mock_point.payload = {"content": "hello"}
        mock_client.scroll.return_value = ([mock_point], "next_offset")

        chunks, offset = store.scroll(limit=1)

        assert len(chunks) == 1
        assert offset == "next_offset"

    def test_init_with_url_uses_server_client(self) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls, patch(
            "ate_rag_kb.vector_store.qdrant_client.ensure_collection"
        ):
            from ate_rag_kb.utils.config import Config

            QdrantVectorStore(Config({"vector_store": {"url": "http://qdrant:6333"}}))

        qdrant_cls.assert_called_once_with(url="http://qdrant:6333")

    def test_init_with_use_local_uses_path_client(self) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls, patch(
            "ate_rag_kb.vector_store.qdrant_client.ensure_collection"
        ):
            from ate_rag_kb.utils.config import Config

            QdrantVectorStore(Config({"vector_store": {"use_local": True, "local_path": "/tmp/qdrant_test"}}))

        qdrant_cls.assert_called_once_with(path="/tmp/qdrant_test")

    def test_init_without_url_or_local_uses_host_port(self) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls, patch(
            "ate_rag_kb.vector_store.qdrant_client.ensure_collection"
        ):
            from ate_rag_kb.utils.config import Config

            QdrantVectorStore(Config({"vector_store": {"host": "qdrant", "port": 9999}}))

        qdrant_cls.assert_called_once_with(host="qdrant", port=9999)

    def test_init_mode_local_uses_path_client(self) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls, patch(
            "ate_rag_kb.vector_store.qdrant_client.ensure_collection"
        ):
            from ate_rag_kb.utils.config import Config

            QdrantVectorStore(
                Config({"vector_store": {"mode": "local", "local_path": "/tmp/qdrant_local"}})
            )

        qdrant_cls.assert_called_once_with(path="/tmp/qdrant_local")

    def test_init_mode_server_with_url_uses_url(self) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls, patch(
            "ate_rag_kb.vector_store.qdrant_client.ensure_collection"
        ):
            from ate_rag_kb.utils.config import Config

            QdrantVectorStore(
                Config({"vector_store": {"mode": "server", "url": "http://qdrant:6333"}})
            )

        qdrant_cls.assert_called_once_with(url="http://qdrant:6333")

    def test_init_mode_server_without_url_uses_host_port(self) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls, patch(
            "ate_rag_kb.vector_store.qdrant_client.ensure_collection"
        ):
            from ate_rag_kb.utils.config import Config

            QdrantVectorStore(
                Config({"vector_store": {"mode": "server", "host": "qdrant", "port": 9999}})
            )

        qdrant_cls.assert_called_once_with(host="qdrant", port=9999)

    def test_init_mode_takes_priority_over_use_local(self) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls, patch(
            "ate_rag_kb.vector_store.qdrant_client.ensure_collection"
        ):
            from ate_rag_kb.utils.config import Config

            QdrantVectorStore(
                Config(
                    {
                        "vector_store": {
                            "mode": "server",
                            "use_local": True,
                            "local_path": "/tmp/qdrant_local",
                        }
                    }
                )
            )

        qdrant_cls.assert_called_once_with(host="localhost", port=6333)

    def test_init_mode_takes_priority_over_url(self) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.QdrantClient") as qdrant_cls, patch(
            "ate_rag_kb.vector_store.qdrant_client.ensure_collection"
        ):
            from ate_rag_kb.utils.config import Config

            QdrantVectorStore(
                Config(
                    {
                        "vector_store": {
                            "mode": "local",
                            "url": "http://qdrant:6333",
                            "local_path": "/tmp/qdrant_local",
                        }
                    }
                )
            )

        qdrant_cls.assert_called_once_with(path="/tmp/qdrant_local")

    def test_clear_collection(self, store: QdrantVectorStore, mock_client: MagicMock) -> None:
        with patch("ate_rag_kb.vector_store.qdrant_client.ensure_collection") as mock_ensure:
            store.clear_collection()

        mock_client.delete_collection.assert_called_once_with(collection_name=store.collection_name)
        mock_ensure.assert_called_once()
