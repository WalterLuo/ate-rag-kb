"""Unit tests for MCP tool handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.mcp.tools import McpToolHandler
from ate_rag_kb.utils.config import Config


class TestMcpToolHandler:
    @pytest.fixture
    def handler(self) -> McpToolHandler:
        pipeline = AsyncMock()
        pipeline.config = Config({"documents": {"igxl": {"enabled": True}}})
        return McpToolHandler(pipeline)

    def _make_handler(self) -> McpToolHandler:
        pipeline = AsyncMock()
        pipeline.config = Config({"documents": {"igxl": {"enabled": True}}})
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
        handler.pipeline.search_enriched = AsyncMock(return_value=[(chunk, 0.9)])

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
        handler.pipeline.retrieve_enriched = AsyncMock(return_value=[(chunk, 0.85)])
        handler.pipeline.get_document = AsyncMock(return_value=[])

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
    async def test_handle_retrieve_job_list_enriched(self) -> None:
        handler = self._make_handler()
        job_list_127 = self._make_chunk(
            chunk_id="jl127",
            source_md="igxl/datatool/DTSheets.11.127.md",
            doc_title="Job List Sheet",
            section_title="Job List Sheet Overview",
            platform="J750",
        )
        job_list_128 = self._make_chunk(
            chunk_id="jl128",
            source_md="igxl/datatool/DTSheets.11.128.md",
            doc_title="Job List Sheet",
            section_title="Job List Sheet Details",
            platform="J750",
        )
        handler.pipeline.retrieve_enriched = AsyncMock(
            return_value=[(job_list_127, 0.95), (job_list_128, 0.9)]
        )
        handler.pipeline.get_document = AsyncMock(return_value=[])

        result = await handler.handle_retrieve(
            {"query": "在 ig-xl 中 job list 有什么用"}
        )

        source_mds = [chunk.source_md for chunk in result.chunks]
        assert "igxl/datatool/DTSheets.11.127.md" in source_mds
        assert "igxl/datatool/DTSheets.11.128.md" in source_mds

    @pytest.mark.asyncio
    async def test_handle_retrieve_adds_array_source_hints(self, handler: McpToolHandler) -> None:
        generic = self._make_chunk(
            chunk_id="generic",
            source_md="29013.md",
            doc_title="DSP_IFFT",
            section_title="Example",
        )
        array_x = self._make_chunk(
            chunk_id="array_x",
            source_md="20847.md",
            doc_title="How to handle ARRAY_x data type",
            section_title="Defining an array",
        )
        array_mtl = self._make_chunk(
            chunk_id="array_mtl",
            source_md="130224.md",
            doc_title="Array in MTL",
            section_title="Array in MTL",
        )
        apg_syntax = self._make_chunk(
            chunk_id="apg_syntax",
            source_md="102025.md",
            doc_title="APG program file syntax",
            section_title="APG program file syntax",
        )
        docs = {
            "20847.md": [array_x],
            "130224.md": [array_mtl],
            "102025.md": [apg_syntax],
        }
        handler.pipeline.retrieve_enriched = AsyncMock(return_value=[(generic, 0.6)])
        handler.pipeline.get_document = AsyncMock(side_effect=lambda source_md: docs[source_md])

        result = await handler.handle_retrieve({"query": "smt7中ARRAY在代码中的作用是什么"})

        source_mds = [chunk.source_md for chunk in result.chunks]
        assert source_mds[:3] == ["20847.md", "130224.md", "102025.md"]
        assert "29013.md" in source_mds
        assert result.context_package is not None
        assert [
            item["source_md"]
            for item in result.context_package.citation_map[:3]
        ] == ["20847.md", "130224.md", "102025.md"]

    @pytest.mark.asyncio
    async def test_handle_ask(self, handler: McpToolHandler) -> None:
        c1 = self._make_chunk(chunk_id="c1", score=0.95)
        c2 = self._make_chunk(chunk_id="c2", score=0.7)
        c3 = self._make_chunk(chunk_id="c3", score=0.6)
        handler.pipeline.search_enriched = AsyncMock(
            return_value=[(c1, 0.95), (c2, 0.7), (c3, 0.6)]
        )
        handler.pipeline.get_document = AsyncMock(return_value=[])

        result = await handler.handle_ask({"question": "how to test?"})

        assert result.question == "how to test?"
        assert result.confidence == "high"
        assert len(result.citations) == 3
        assert result.citations[0].chunk_id == "c1"
        assert result.citations[0].source_md == "doc.md"
        assert result.source_files == ["doc.md"]
        assert result.context_package is not None

    @pytest.mark.asyncio
    async def test_handle_ask_adds_array_source_hints(self, handler: McpToolHandler) -> None:
        generic = self._make_chunk(
            chunk_id="generic",
            source_md="30471.md",
            doc_title="DSP_SETTLING",
            section_title="Example",
        )
        array_x = self._make_chunk(
            chunk_id="array_x",
            source_md="20847.md",
            doc_title="How to handle ARRAY_x data type",
            section_title="Defining an array",
        )
        array_mtl = self._make_chunk(
            chunk_id="array_mtl",
            source_md="130224.md",
            doc_title="Array in MTL",
            section_title="Array in MTL",
        )
        apg_syntax = self._make_chunk(
            chunk_id="apg_syntax",
            source_md="102025.md",
            doc_title="APG program file syntax",
            section_title="APG program file syntax",
        )
        docs = {
            "20847.md": [array_x],
            "130224.md": [array_mtl],
            "102025.md": [apg_syntax],
        }
        handler.pipeline.search_enriched = AsyncMock(return_value=[(generic, 0.6)])
        handler.pipeline.get_document = AsyncMock(side_effect=lambda source_md: docs[source_md])

        result = await handler.handle_ask({"question": "smt7中ARRAY在代码中的作用是什么"})

        assert result.source_files[:3] == ["102025.md", "130224.md", "20847.md"]
        assert [citation.source_md for citation in result.citations[:3]] == [
            "20847.md",
            "130224.md",
            "102025.md",
        ]
        assert result.context_package is not None
        assert [
            item["source_md"]
            for item in result.context_package.citation_map[:3]
        ] == ["20847.md", "130224.md", "102025.md"]

    @pytest.mark.asyncio
    async def test_handle_ask_low_confidence(self, handler: McpToolHandler) -> None:
        chunk = self._make_chunk(score=0.3)
        handler.pipeline.search_enriched = AsyncMock(return_value=[(chunk, 0.3)])

        result = await handler.handle_ask({"question": "vague?"})

        assert result.confidence == "low"

    @pytest.mark.asyncio
    async def test_handle_get_document(self, handler: McpToolHandler) -> None:
        chunk = self._make_chunk()
        handler.pipeline.get_document_page = AsyncMock(
            return_value={
                "chunks": [chunk],
                "total": 1,
                "returned": 1,
                "has_more": False,
                "next_offset": None,
            }
        )

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
        handler.pipeline.get_document_page.assert_awaited_once_with("doc.md", limit=20, offset=0)

    @pytest.mark.asyncio
    async def test_handle_get_document_pagination_limit(self, handler: McpToolHandler) -> None:
        chunks = [self._make_chunk(chunk_id=f"c{i}") for i in range(5)]
        handler.pipeline.get_document_page = AsyncMock(
            return_value={
                "chunks": chunks[:2],
                "total": 5,
                "returned": 2,
                "has_more": True,
                "next_offset": 2,
            }
        )

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
        handler.pipeline.get_document_page = AsyncMock(
            return_value={
                "chunks": chunks[2:4],
                "total": 5,
                "returned": 2,
                "has_more": True,
                "next_offset": 4,
            }
        )

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
        handler.pipeline.get_document_page = AsyncMock(
            return_value={
                "chunks": chunks[2:],
                "total": 3,
                "returned": 1,
                "has_more": False,
                "next_offset": None,
            }
        )

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
        handler.pipeline.get_document_page = AsyncMock(
            return_value={
                "chunks": chunks,
                "total": 10,
                "returned": 10,
                "has_more": False,
                "next_offset": None,
            }
        )

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

    # -----------------------------------------------------------------------
    # IG-XL source hints (15Q evaluation follow-up)
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("query", "expected_sources"),
        [
            (
                "DSIO200 的 VSSS/VSSC 是什么",
                (
                    "igxl/patternlanguage/plinstruments.5.07.md",
                    "igxl/dibdesign/dib_hsd200.16.5.md",
                ),
            ),
            (
                "IG-XL SECS/GEM spooling CONTROLSTATE",
                ("igxl/secsgem/secs_scenario.11.51.md",),
            ),
            (
                "IG-XL SECS/GEM spooling 在什么 CONTROLSTATE 下有意义",
                ("igxl/secsgem/secs_scenario.11.51.md",),
            ),
            (
                "Test Analysis Tool startup",
                ("igxl/testanalysis/taUsing.1.2.md",),
            ),
            (
                "Available J750 Features",
                ("igxl/igxladmin/adLicensing.2.6.md",),
            ),
            (
                "Available J750 Features 文档说明 J750 features 按哪些 instrument 或 feature 分类",
                ("igxl/igxladmin/adLicensing.2.6.md",),
            ),
            (
                "MTO Pattern Microcodes",
                (
                    "igxl/patternlanguage/plmto.7.03.md",
                    "igxl/patterntool/PTVectorsEditing.4.21.md",
                ),
            ),
            (
                "Programming the MTO Resource Map",
                ("igxl/mto800/mt800prog.3.04.md",),
            ),
            (
                "MTO Resource Map Sheet programming restrictions",
                (
                    "igxl/datatool/DTSheets.11.185.md",
                    "igxl/mto800/mt800prog.3.04.md",
                ),
            ),
            (
                "MTO800 中 Programming the MTO Resource Map 应该查看哪个文档",
                ("igxl/mto800/mt800prog.3.04.md",),
            ),
            (
                "DataTool 中 MTO Resource Map Sheet 的 programming restrictions 和 configuration limitations",
                (
                    "igxl/datatool/DTSheets.11.185.md",
                    "igxl/mto800/mt800prog.3.04.md",
                ),
            ),
            (
                "Pattern Tool 中如果 pattern file 使用 MTO，Vectors worksheet 会有什么额外内容",
                (
                    "igxl/patterntool/PTVectorsEditing.4.21.md",
                    "igxl/patternlanguage/plmto.7.03.md",
                ),
            ),
        ],
    )
    def test_source_hints_for_igxl_weak_topics(
        self, query: str, expected_sources: tuple[str, ...]
    ) -> None:
        handler = self._make_handler()
        _, source_mds = handler._source_hints_for_query(query)
        assert source_mds == expected_sources
        assert all(not src.startswith(("smt7/", "v93000/")) for src in source_mds)

    def test_source_hints_drop_igxl_when_disabled(self) -> None:
        pipeline = AsyncMock()
        pipeline.config = Config({"documents": {"igxl": {"enabled": False}}})
        handler = McpToolHandler(pipeline)
        _, source_mds = handler._source_hints_for_query("DSIO200 VSSS")
        assert source_mds == ()

    def test_source_hints_preserve_igxl_when_enabled(self) -> None:
        handler = self._make_handler()
        _, source_mds = handler._source_hints_for_query("DSIO200 VSSS")
        assert "igxl/patternlanguage/plinstruments.5.07.md" in source_mds

    def test_select_source_hint_chunk_prefers_term_match(self) -> None:
        chunk1 = Chunk(
            id="c1",
            content="general intro",
            chunk_type=ChunkType.PARAGRAPH,
            doc_title="Intro",
        )
        chunk2 = Chunk(
            id="c2",
            content="VSSS and VSSC details",
            chunk_type=ChunkType.PARAGRAPH,
            doc_title="DSIO200",
        )
        result = McpToolHandler._select_source_hint_chunk(
            "DSIO200 VSSS", [chunk1, chunk2], ("vsss", "vssc")
        )
        assert result is not None
        assert result.id == "c2"

    @pytest.mark.asyncio
    async def test_handle_retrieve_adds_igxl_dsio200_source_hints(self) -> None:
        handler = self._make_handler()
        generic = self._make_chunk(
            chunk_id="generic",
            source_md="igxl/relnotesprev/ReadMe_V3.50.50.4.20.md",
            doc_title="Release Notes",
        )
        vsss = self._make_chunk(
            chunk_id="vsss",
            source_md="igxl/patternlanguage/plinstruments.5.07.md",
            doc_title="Pattern Language Instruments",
            section_title="DSIO200 VSSS/VSSC",
        )
        vssc = self._make_chunk(
            chunk_id="vssc",
            source_md="igxl/dibdesign/dib_hsd200.16.5.md",
            doc_title="DIB Design",
            section_title="HSD200",
        )
        docs = {
            "igxl/patternlanguage/plinstruments.5.07.md": [vsss],
            "igxl/dibdesign/dib_hsd200.16.5.md": [vssc],
        }
        handler.pipeline.retrieve_enriched = AsyncMock(return_value=[(generic, 0.6)])
        handler.pipeline.get_document = AsyncMock(
            side_effect=lambda source_md: docs.get(source_md, [])
        )

        result = await handler.handle_retrieve({"query": "DSIO200 的 VSSS/VSSC 是什么"})

        source_mds = [chunk.source_md for chunk in result.chunks]
        assert source_mds[:2] == [
            "igxl/patternlanguage/plinstruments.5.07.md",
            "igxl/dibdesign/dib_hsd200.16.5.md",
        ]
        assert all(not src.startswith(("smt7/", "v93000/")) for src in source_mds)

    @pytest.mark.asyncio
    async def test_handle_ask_adds_igxl_secsgem_spooling_hint(self) -> None:
        handler = self._make_handler()
        generic = self._make_chunk(
            chunk_id="generic",
            source_md="igxl/datatool/dtribbon.03.10.md",
            doc_title="DataTool Ribbon",
        )
        spooling = self._make_chunk(
            chunk_id="spooling",
            source_md="igxl/secsgem/secs_scenario.11.51.md",
            doc_title="SECS Scenario",
            section_title="Spooling CONTROLSTATE",
        )
        docs = {"igxl/secsgem/secs_scenario.11.51.md": [spooling]}
        handler.pipeline.search_enriched = AsyncMock(return_value=[(generic, 0.6)])
        handler.pipeline.get_document = AsyncMock(
            side_effect=lambda source_md: docs.get(source_md, [])
        )

        result = await handler.handle_ask(
            {"question": "IG-XL SECS/GEM spooling 在什么 CONTROLSTATE 下有意义"}
        )

        assert "igxl/secsgem/secs_scenario.11.51.md" in result.source_files
        assert all(not src.startswith(("smt7/", "v93000/")) for src in result.source_files)
        assert result.citations[0].source_md == "igxl/secsgem/secs_scenario.11.51.md"

    @pytest.mark.asyncio
    async def test_handle_ask_adds_mto_resource_map_hint(self) -> None:
        handler = self._make_handler()
        generic = self._make_chunk(
            chunk_id="generic",
            source_md="igxl/datatool/dtribbon.03.10.md",
            doc_title="DataTool Ribbon",
        )
        resource_map = self._make_chunk(
            chunk_id="resource_map",
            source_md="igxl/mto800/mt800prog.3.04.md",
            doc_title="MTO800 Programming",
            section_title="Programming the MTO Resource Map",
        )
        docs = {"igxl/mto800/mt800prog.3.04.md": [resource_map]}
        handler.pipeline.search_enriched = AsyncMock(return_value=[(generic, 0.6)])
        handler.pipeline.get_document = AsyncMock(
            side_effect=lambda source_md: docs.get(source_md, [])
        )

        result = await handler.handle_ask(
            {"question": "MTO800 中 Programming the MTO Resource Map 应该查看哪个文档"}
        )

        assert "igxl/mto800/mt800prog.3.04.md" in result.source_files
        assert all(not src.startswith(("smt7/", "v93000/")) for src in result.source_files)
        assert result.citations[0].source_md == "igxl/mto800/mt800prog.3.04.md"

    @pytest.mark.asyncio
    async def test_handle_ask_adds_mto_datatool_restrictions_hint(self) -> None:
        handler = self._make_handler()
        generic = self._make_chunk(
            chunk_id="generic",
            source_md="igxl/datatool/dtribbon.03.10.md",
            doc_title="DataTool Ribbon",
        )
        sheet = self._make_chunk(
            chunk_id="sheet",
            source_md="igxl/datatool/DTSheets.11.185.md",
            doc_title="DataTool Sheets",
            section_title="MTO Resource Map Sheet",
        )
        resource_map = self._make_chunk(
            chunk_id="resource_map",
            source_md="igxl/mto800/mt800prog.3.04.md",
            doc_title="MTO800 Programming",
            section_title="Programming the MTO Resource Map",
        )
        docs = {
            "igxl/datatool/DTSheets.11.185.md": [sheet],
            "igxl/mto800/mt800prog.3.04.md": [resource_map],
        }
        handler.pipeline.search_enriched = AsyncMock(return_value=[(generic, 0.6)])
        handler.pipeline.get_document = AsyncMock(
            side_effect=lambda source_md: docs.get(source_md, [])
        )

        result = await handler.handle_ask(
            {
                "question": "DataTool 中 MTO Resource Map Sheet 的 programming restrictions 和 configuration limitations"
            }
        )

        source_mds = result.source_files
        assert "igxl/datatool/DTSheets.11.185.md" in source_mds
        assert "igxl/mto800/mt800prog.3.04.md" in source_mds
        assert all(not src.startswith(("smt7/", "v93000/")) for src in source_mds)
        assert all(
            not src.split("/")[-1].split(".")[0].isdigit() for src in source_mds
        )

    # -----------------------------------------------------------------------
    # IG-XL contamination filtering (Q8 follow-up)
    # -----------------------------------------------------------------------

    def test_is_igxl_query_detects_igxl_context(self) -> None:
        assert McpToolHandler._is_igxl_query("IG-XL SECS/GEM spooling") is True
        assert McpToolHandler._is_igxl_query("J750 license management") is True
        assert McpToolHandler._is_igxl_query("Pattern Tool MTO vectors") is True
        assert McpToolHandler._is_igxl_query("How does V93000 pattern tool work") is False
        assert McpToolHandler._is_igxl_query("SMT7 array handling") is False

    def test_is_smt7_or_v93000_chunk_detects_numeric_and_prefix_docs(self) -> None:
        smt7_prefixed = self._make_chunk(source_md="smt7/pattern/119474.md")
        v93000_prefixed = self._make_chunk(source_md="v93000/timing/levels.md")
        numeric_only = self._make_chunk(source_md="119474.md")
        numeric_variant = self._make_chunk(source_md="119474_2.md")
        igxl_doc = self._make_chunk(source_md="igxl/patterntool/PTVectorsEditing.4.21.md")

        assert McpToolHandler._is_smt7_or_v93000_chunk(smt7_prefixed) is True
        assert McpToolHandler._is_smt7_or_v93000_chunk(v93000_prefixed) is True
        assert McpToolHandler._is_smt7_or_v93000_chunk(numeric_only) is True
        assert McpToolHandler._is_smt7_or_v93000_chunk(numeric_variant) is True
        assert McpToolHandler._is_smt7_or_v93000_chunk(igxl_doc) is False

    def test_filter_igxl_contamination_removes_smt7_for_igxl_queries(self) -> None:
        igxl_chunk = self._make_chunk(source_md="igxl/patterntool/PTVectorsEditing.4.21.md")
        smt7_chunk = self._make_chunk(source_md="119474.md")
        v93000_chunk = self._make_chunk(source_md="v93000/timing/levels.md")
        results = [(igxl_chunk, 0.9), (smt7_chunk, 0.85), (v93000_chunk, 0.8)]

        filtered = McpToolHandler._filter_igxl_contamination(
            "Pattern Tool 中如果 pattern file 使用 MTO", results
        )

        source_mds = [c.source_md for c, _ in filtered]
        assert source_mds == ["igxl/patterntool/PTVectorsEditing.4.21.md"]

    def test_filter_igxl_contamination_preserves_all_for_neutral_queries(self) -> None:
        igxl_chunk = self._make_chunk(source_md="igxl/patterntool/PTVectorsEditing.4.21.md")
        smt7_chunk = self._make_chunk(source_md="119474.md")
        results = [(igxl_chunk, 0.9), (smt7_chunk, 0.85)]

        filtered = McpToolHandler._filter_igxl_contamination(
            "How does testing work in general", results
        )

        assert len(filtered) == 2

    @pytest.mark.asyncio
    async def test_handle_ask_filters_smt7_contamination_for_igxl_query(self) -> None:
        handler = self._make_handler()
        igxl_chunk = self._make_chunk(
            chunk_id="igxl",
            source_md="igxl/patterntool/PTVectorsEditing.4.21.md",
            doc_title="Pattern Tool Vectors",
        )
        smt7_chunk = self._make_chunk(
            chunk_id="smt7",
            source_md="119474.md",
            doc_title="Pattern Tool MTO",
        )
        handler.pipeline.search_enriched = AsyncMock(
            return_value=[(igxl_chunk, 0.9), (smt7_chunk, 0.85)]
        )
        handler.pipeline.get_document = AsyncMock(return_value=[])

        result = await handler.handle_ask(
            {"question": "Pattern Tool 中如果 pattern file 使用 MTO，Vectors worksheet 会有什么额外内容"}
        )

        assert all(not src.startswith(("smt7/", "v93000/")) for src in result.source_files)
        assert "119474.md" not in result.source_files
        assert "igxl/patterntool/PTVectorsEditing.4.21.md" in result.source_files

    # -----------------------------------------------------------------------
    # Planner-driven retrieval & bidirectional ecosystem filtering
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_ask_job_list_chinese(self) -> None:
        handler = self._make_handler()
        job_list_127 = self._make_chunk(
            chunk_id="jl127",
            source_md="igxl/datatool/DTSheets.11.127.md",
            doc_title="Job List Sheet",
            section_title="Job List Sheet Overview",
            platform="J750",
        )
        job_list_128 = self._make_chunk(
            chunk_id="jl128",
            source_md="igxl/datatool/DTSheets.11.128.md",
            doc_title="Job List Sheet",
            section_title="Job List Sheet Details",
            platform="J750",
        )
        numeric_contam = self._make_chunk(
            chunk_id="smt7",
            source_md="119474.md",
            doc_title="SMT7 Pattern",
            platform="SMT7",
        )
        handler.pipeline.search_enriched = AsyncMock(
            return_value=[
                (job_list_127, 0.95),
                (job_list_128, 0.9),
                (numeric_contam, 0.85),
            ]
        )
        handler.pipeline.get_document = AsyncMock(return_value=[])

        result = await handler.handle_ask(
            {"question": "在 ig-xl 中 job list 有什么用"}
        )

        source_mds = result.source_files
        assert "igxl/datatool/DTSheets.11.127.md" in source_mds
        assert "igxl/datatool/DTSheets.11.128.md" in source_mds
        assert "119474.md" not in source_mds

    @pytest.mark.asyncio
    async def test_handle_ask_job_list_glossary(self) -> None:
        handler = self._make_handler()
        job_list = self._make_chunk(
            chunk_id="jl",
            source_md="igxl/datatool/DTSheets.11.127.md",
            doc_title="Job List Sheet",
            platform="J750",
        )
        handler.pipeline.search_enriched = AsyncMock(
            return_value=[(job_list, 0.95)]
        )
        handler.pipeline.get_document = AsyncMock(return_value=[])

        result = await handler.handle_ask({"question": "作业列表有什么用"})

        assert "igxl/datatool/DTSheets.11.127.md" in result.source_files

    @pytest.mark.asyncio
    async def test_handle_ask_preserves_enrichment_beyond_top_k(self) -> None:
        handler = self._make_handler()
        primary = [
            self._make_chunk(chunk_id=f"p{i}", source_md=f"igxl/doc{i}.md", platform="J750")
            for i in range(3)
        ]
        doc_context = self._make_chunk(
            chunk_id="doc",
            source_md="igxl/datatool/DTSheets.11.127.md",
            doc_title="Job List Sheet",
            platform="J750",
        )
        handler.pipeline.search_enriched = AsyncMock(
            return_value=[(chunk, 0.9 - i * 0.1) for i, chunk in enumerate(primary)]
            + [(doc_context, 0.5)]
        )
        handler.pipeline.get_document = AsyncMock(return_value=[])

        result = await handler.handle_ask(
            {"question": "在 ig-xl 中 job list 有什么用", "top_k": 3}
        )

        assert len(result.citations) == 4
        assert "igxl/datatool/DTSheets.11.127.md" in result.source_files

    @pytest.mark.asyncio
    async def test_handle_ask_smt7_array_not_contaminated(self) -> None:
        handler = self._make_handler()
        smt7_array = self._make_chunk(
            chunk_id="smt7_array",
            source_md="smt7/programming/arrays.md",
            doc_title="SMT7 Arrays",
            platform="SMT7",
        )
        igxl_array = self._make_chunk(
            chunk_id="igxl_array",
            source_md="igxl/patternlanguage/plarrays.1.01.md",
            doc_title="IG-XL Arrays",
            platform="J750",
        )
        handler.pipeline.search_enriched = AsyncMock(
            return_value=[(smt7_array, 0.9), (igxl_array, 0.85)]
        )
        handler.pipeline.get_document = AsyncMock(return_value=[])

        result = await handler.handle_ask({"question": "SMT7 ARRAY"})

        source_mds = result.source_files
        assert "smt7/programming/arrays.md" in source_mds
        assert "igxl/patternlanguage/plarrays.1.01.md" not in source_mds

    @pytest.mark.asyncio
    async def test_handle_ask_tdc_recognized_as_v93000(self) -> None:
        handler = self._make_handler()
        tdc_doc = self._make_chunk(
            chunk_id="tdc",
            source_md="119474.md",
            doc_title="TDC Flow Creator",
            platform="TDC",
        )
        igxl_doc = self._make_chunk(
            chunk_id="igxl",
            source_md="igxl/datatool/dtribbon.03.10.md",
            doc_title="DataTool Ribbon",
            platform="J750",
        )
        handler.pipeline.search_enriched = AsyncMock(
            return_value=[(tdc_doc, 0.9), (igxl_doc, 0.85)]
        )
        handler.pipeline.get_document = AsyncMock(return_value=[])

        result = await handler.handle_ask({"question": "TDC 中如何查看文档"})

        source_mds = result.source_files
        assert "119474.md" in source_mds
        assert "igxl/datatool/dtribbon.03.10.md" not in source_mds

    @pytest.mark.asyncio
    async def test_bidirectional_filter_v93000_excludes_igxl(self) -> None:
        handler = self._make_handler()
        v93000_doc = self._make_chunk(
            chunk_id="v93000",
            source_md="v93000/timing/levels.md",
            doc_title="V93000 Levels",
            platform="V93000",
        )
        igxl_doc = self._make_chunk(
            chunk_id="igxl",
            source_md="igxl/patterntool/PTVectorsEditing.4.21.md",
            doc_title="Pattern Tool",
            platform="J750",
        )
        handler.pipeline.search_enriched = AsyncMock(
            return_value=[(v93000_doc, 0.9), (igxl_doc, 0.85)]
        )
        handler.pipeline.get_document = AsyncMock(return_value=[])

        result = await handler.handle_ask({"question": "v93000 levels"})

        source_mds = result.source_files
        assert "v93000/timing/levels.md" in source_mds
        assert "igxl/patterntool/PTVectorsEditing.4.21.md" not in source_mds
