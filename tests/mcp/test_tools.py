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
    async def test_handle_get_document(self, handler: McpToolHandler) -> None:
        chunk = self._make_chunk()
        handler.pipeline.get_document = AsyncMock(return_value=[chunk])

        result = await handler.handle_get_document({"source_md": "doc.md"})

        assert result.source_md == "doc.md"
        assert result.total == 1
        assert result.returned == 1
        assert result.offset == 0
        assert result.limit == 20
        assert result.has_more is False
        assert result.next_offset is None
        assert result.chunks[0].id == "c1"
        assert result.context_package is not None

    @pytest.mark.asyncio
    async def test_handle_get_document_pagination_limit(self, handler: McpToolHandler) -> None:
        chunks = [self._make_chunk(chunk_id=f"c{i}") for i in range(5)]
        handler.pipeline.get_document = AsyncMock(return_value=chunks)

        result = await handler.handle_get_document({"source_md": "doc.md", "limit": 2})

        assert result.total == 5
        assert result.returned == 2
        assert result.limit == 2
        assert result.has_more is True
        assert result.next_offset == 2
        assert [c.id for c in result.chunks] == ["c0", "c1"]

    @pytest.mark.asyncio
    async def test_handle_get_document_pagination_offset(self, handler: McpToolHandler) -> None:
        chunks = [self._make_chunk(chunk_id=f"c{i}") for i in range(5)]
        handler.pipeline.get_document = AsyncMock(return_value=chunks)

        result = await handler.handle_get_document({"source_md": "doc.md", "limit": 2, "offset": 2})

        assert result.total == 5
        assert result.returned == 2
        assert result.offset == 2
        assert result.has_more is True
        assert result.next_offset == 4
        assert [c.id for c in result.chunks] == ["c2", "c3"]

    @pytest.mark.asyncio
    async def test_handle_get_document_pagination_last_page(self, handler: McpToolHandler) -> None:
        chunks = [self._make_chunk(chunk_id=f"c{i}") for i in range(3)]
        handler.pipeline.get_document = AsyncMock(return_value=chunks)

        result = await handler.handle_get_document({"source_md": "doc.md", "limit": 2, "offset": 2})

        assert result.total == 3
        assert result.returned == 1
        assert result.offset == 2
        assert result.has_more is False
        assert result.next_offset is None
        assert [c.id for c in result.chunks] == ["c2"]

    @pytest.mark.asyncio
    async def test_handle_get_document_max_tokens(self, handler: McpToolHandler) -> None:
        chunks = [self._make_chunk(chunk_id=f"c{i}", content="x" * 400) for i in range(10)]
        handler.pipeline.get_document = AsyncMock(return_value=chunks)

        result = await handler.handle_get_document({"source_md": "doc.md", "max_tokens": 500})

        assert result.total == 10
        assert result.context_package is not None
        # build_context_package stops after exceeding max_tokens, so the estimate
        # may slightly overshoot one chunk; verify not all 10 chunks were included.
        assert result.context_package.token_estimate < 1200
        assert len(result.context_package.citation_map) < 10

    @pytest.mark.asyncio
    async def test_handle_related(self, handler: McpToolHandler) -> None:
        parent = self._make_chunk(chunk_id="p1", content="parent")
        sibling1 = self._make_chunk(chunk_id="s1", content="sibling1")
        sibling2 = self._make_chunk(chunk_id="s2", content="sibling2")
        sibling3 = self._make_chunk(chunk_id="s3", content="sibling3")
        handler.pipeline.get_related = AsyncMock(
            return_value={"parent": parent, "siblings": [sibling1, sibling2, sibling3], "children": []}
        )

        result = await handler.handle_related({"chunk_id": "c1"})

        assert result.chunk_id == "c1"
        assert result.parent is not None
        assert result.parent.id == "p1"
        assert len(result.siblings) == 2
        assert result.siblings[0].id == "s1"
        assert result.siblings[1].id == "s2"
        assert len(result.children) == 0

    @pytest.mark.asyncio
    async def test_handle_related_max_siblings_1(self, handler: McpToolHandler) -> None:
        s1 = self._make_chunk(chunk_id="s1")
        s2 = self._make_chunk(chunk_id="s2")
        s3 = self._make_chunk(chunk_id="s3")
        handler.pipeline.get_related = AsyncMock(
            return_value={"parent": None, "siblings": [s1, s2, s3], "children": []}
        )

        result = await handler.handle_related({"chunk_id": "c1", "max_siblings": 1})

        assert len(result.siblings) == 1
        assert result.siblings[0].id == "s1"

    @pytest.mark.asyncio
    async def test_handle_related_max_siblings_0(self, handler: McpToolHandler) -> None:
        s1 = self._make_chunk(chunk_id="s1")
        s2 = self._make_chunk(chunk_id="s2")
        handler.pipeline.get_related = AsyncMock(
            return_value={"parent": None, "siblings": [s1, s2], "children": []}
        )

        result = await handler.handle_related({"chunk_id": "c1", "max_siblings": 0})

        assert len(result.siblings) == 0

    @pytest.mark.asyncio
    async def test_handle_related_no_siblings(self, handler: McpToolHandler) -> None:
        s1 = self._make_chunk(chunk_id="s1")
        s2 = self._make_chunk(chunk_id="s2")
        handler.pipeline.get_related = AsyncMock(
            return_value={"parent": None, "siblings": [s1, s2], "children": []}
        )

        result = await handler.handle_related({"chunk_id": "c1", "include_siblings": False})

        assert len(result.siblings) == 0

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
