"""Unit tests for MCP tool handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.mcp.tools import McpToolHandler


class TestMcpToolHandler:
    @pytest.fixture
    def handler(self) -> McpToolHandler:
        pipeline = AsyncMock()
        return McpToolHandler(pipeline)

    def _make_chunk(
        self,
        chunk_id: str = "c1",
        content: str = "test content",
        score: float = 0.9,
        source_md: str = "doc.md",
        doc_title: str = "Doc Title",
        section_title: str = "Section",
        platform: str = "TDC",
        start_line: int = 10,
        end_line: int = 20,
    ) -> Chunk:
        return Chunk(
            id=chunk_id,
            content=content,
            chunk_type=ChunkType.PARAGRAPH,
            source_md=source_md,
            doc_title=doc_title,
            section_title=section_title,
            platform=platform,
            start_line=start_line,
            end_line=end_line,
            score=score,
        )

    @pytest.mark.asyncio
    async def test_handle_search(self, handler: McpToolHandler) -> None:
        chunk = self._make_chunk()
        handler.pipeline.search = AsyncMock(return_value=[(chunk, 0.9)])

        result = await handler.handle_search({"query": "test"})

        assert result.query == "test"
        assert result.total == 1
        assert result.chunks[0].id == "c1"
        assert result.chunks[0].source_md == "doc.md"
        assert result.chunks[0].doc_title == "Doc Title"
        assert result.chunks[0].section_title == "Section"
        assert result.chunks[0].start_line == 10
        assert result.chunks[0].end_line == 20
        assert len(result.sources) == 1
        assert result.sources[0]["source_md"] == "doc.md"

    @pytest.mark.asyncio
    async def test_handle_retrieve(self, handler: McpToolHandler) -> None:
        chunk = self._make_chunk()
        handler.pipeline.retrieve = AsyncMock(return_value=[(chunk, 0.85)])

        result = await handler.handle_retrieve({"query": "test"})

        assert result.query == "test"
        assert result.total == 1
        assert result.processing["reranked"] is True
        assert result.processing["expanded"] is True
        assert result.processing["compressed"] is True
        assert result.context_package is not None
        assert len(result.context_package.citation_map) == 1
        assert result.context_package.citation_map[0]["source_md"] == "doc.md"

    @pytest.mark.asyncio
    async def test_handle_ask(self, handler: McpToolHandler) -> None:
        c1 = self._make_chunk(chunk_id="c1", score=0.95)
        c2 = self._make_chunk(chunk_id="c2", score=0.7)
        c3 = self._make_chunk(chunk_id="c3", score=0.6)
        handler.pipeline.search = AsyncMock(return_value=[(c1, 0.95), (c2, 0.7), (c3, 0.6)])

        result = await handler.handle_ask({"question": "how to test?"})

        assert result.question == "how to test?"
        assert result.confidence == "high"
        assert len(result.citations) == 3
        assert result.citations[0].chunk_id == "c1"
        assert result.citations[0].source_md == "doc.md"
        assert result.source_files == ["doc.md"]
        assert result.context_package is not None

    @pytest.mark.asyncio
    async def test_handle_ask_low_confidence(self, handler: McpToolHandler) -> None:
        chunk = self._make_chunk(score=0.3)
        handler.pipeline.search = AsyncMock(return_value=[(chunk, 0.3)])

        result = await handler.handle_ask({"question": "vague?"})

        assert result.confidence == "low"

    @pytest.mark.asyncio
    async def test_handle_related(self, handler: McpToolHandler) -> None:
        parent = self._make_chunk(chunk_id="p1", content="parent")
        sibling = self._make_chunk(chunk_id="s1", content="sibling")
        handler.pipeline.get_related = AsyncMock(
            return_value={"parent": parent, "siblings": [sibling], "children": []}
        )

        result = await handler.handle_related({"chunk_id": "c1"})

        assert result.chunk_id == "c1"
        assert result.parent is not None
        assert result.parent.id == "p1"
        assert len(result.siblings) == 1
        assert result.siblings[0].id == "s1"
        assert len(result.children) == 0

    @pytest.mark.asyncio
    async def test_handle_get_document(self, handler: McpToolHandler) -> None:
        chunk = self._make_chunk()
        handler.pipeline.get_document = AsyncMock(return_value=[chunk])

        result = await handler.handle_get_document({"source_md": "doc.md"})

        assert result.source_md == "doc.md"
        assert result.total == 1
        assert result.chunks[0].id == "c1"

    @pytest.mark.asyncio
    async def test_handle_status(self, handler: McpToolHandler) -> None:
        handler.pipeline.collection_stats = AsyncMock(
            return_value={
                "collection_name": "ate_kb",
                "total_chunks": 100,
                "vector_size": 1024,
                "embedding_model": "bge-m3",
                "platforms": ["TDC"],
                "doc_types": ["reference"],
            }
        )

        result = await handler.handle_status({})

        assert result.status == "ok"
        assert result.collection_name == "ate_kb"
        assert result.total_chunks == 100
        assert result.vector_size == 1024
        assert result.platforms == ["TDC"]

    @pytest.mark.asyncio
    async def test_handle_status_degraded(self, handler: McpToolHandler) -> None:
        handler.pipeline.collection_stats = AsyncMock(side_effect=RuntimeError("fail"))

        result = await handler.handle_status({})

        assert result.status == "degraded"
