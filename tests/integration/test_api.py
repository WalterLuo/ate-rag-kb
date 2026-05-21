"""Integration tests for FastAPI endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ate_rag_kb.api.server import create_app
from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.utils.config import Config


@pytest.fixture
def mock_retriever() -> AsyncMock:
    retriever = AsyncMock()
    retriever.search.return_value = [
        (
            Chunk(
                id="c1",
                content="Test content",
                chunk_type=ChunkType.PARAGRAPH,
                doc_title="Doc",
                source_md="doc.md",
                score=0.95,
            ),
            0.95,
        )
    ]
    retriever.retrieve.return_value = [
        (
            Chunk(
                id="c1",
                content="Test content",
                chunk_type=ChunkType.PARAGRAPH,
                doc_title="Doc",
                source_md="doc.md",
                score=0.95,
            ),
            0.95,
        )
    ]
    retriever.get_related.return_value = {
        "parent": Chunk(id="p1", content="Parent", chunk_type=ChunkType.SECTION),
        "siblings": [],
        "children": [],
    }
    retriever.get_document.return_value = [
        Chunk(id="c1", content="Test", chunk_type=ChunkType.PARAGRAPH, source_md="doc.md"),
    ]
    return retriever


@pytest.fixture
def client(mock_retriever: AsyncMock) -> TestClient:
    config = Config({"logging": {"level": "INFO", "format": "json"}})
    app = create_app(config)

    from ate_rag_kb.api.routes import set_retriever

    set_retriever(mock_retriever)
    return TestClient(app)


class TestHealth:
    def test_health_endpoint(self, client: TestClient) -> None:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSearch:
    def test_search_returns_chunks(self, client: TestClient) -> None:
        response = client.post("/api/v1/search", json={"query": "test query"})

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert len(data["chunks"]) == 1
        assert data["chunks"][0]["id"] == "c1"

    def test_search_with_filters(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/search",
            json={"query": "test", "filters": {"platform": "TDC"}},
        )

        assert response.status_code == 200

    def test_search_rejects_empty_query(self, client: TestClient) -> None:
        response = client.post("/api/v1/search", json={"query": ""})

        assert response.status_code == 422


class TestRetrieve:
    def test_retrieve_with_expansion(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/retrieve",
            json={
                "query": "test",
                "expand_parents": True,
                "expand_siblings": True,
                "rerank": True,
                "compress": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reranked"] is True
        assert data["expanded"] is True
        assert data["compressed"] is True

    def test_retrieve_rejects_empty_query(self, client: TestClient) -> None:
        response = client.post("/api/v1/retrieve", json={"query": ""})

        assert response.status_code == 422


class TestAsk:
    def test_ask_returns_citations(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/ask",
            json={"question": "What is TDC?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["question"] == "What is TDC?"
        assert len(data["citations"]) == 1
        assert data["citations"][0]["chunk_id"] == "c1"

    def test_ask_rejects_empty_question(self, client: TestClient) -> None:
        response = client.post("/api/v1/ask", json={"question": ""})

        assert response.status_code == 422


class TestRelated:
    def test_related_returns_parent(self, client: TestClient) -> None:
        response = client.post("/api/v1/related", json={"chunk_id": "c1"})

        assert response.status_code == 200
        data = response.json()
        assert data["chunk_id"] == "c1"
        assert data["parent"]["id"] == "p1"

    def test_related_rejects_empty_chunk_id(self, client: TestClient) -> None:
        response = client.post("/api/v1/related", json={"chunk_id": ""})

        assert response.status_code == 422


class TestDocument:
    def test_get_document_returns_chunks(self, client: TestClient) -> None:
        response = client.get("/api/v1/document/doc.md")

        assert response.status_code == 200
        data = response.json()
        assert data["source_md"] == "doc.md"
        assert len(data["chunks"]) == 1
