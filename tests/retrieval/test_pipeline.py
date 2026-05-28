"""Unit tests for RetrievalPipeline search_enriched and retrieve_enriched."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.retrieval.pipeline import RetrievalPipeline
from ate_rag_kb.retrieval.planner import RetrievalPlanner
from ate_rag_kb.utils.config import Config


class TestSearchEnriched:
    @pytest.fixture
    def pipeline(self) -> RetrievalPipeline:
        config = Config(
            {
                "retrieval": {
                    "planner": {
                        "title_boost_factor": 0.15,
                        "context_enrichment_enabled": True,
                        "enrichment_budget": 3,
                    },
                    "vector_search": {"top_k": 20},
                    "bm25_search": {"enabled": True, "top_k": 20},
                    "hybrid": {
                        "enabled": True,
                        "vector_weight": 0.7,
                        "bm25_weight": 0.3,
                        "final_top_k": 10,
                    },
                    "reranker": {"enabled": True, "top_k": 5},
                    "parent_child": {
                        "enabled": True,
                        "include_parent": True,
                        "include_siblings": True,
                    },
                    "compression": {"enabled": True, "max_tokens": 4000},
                },
                "embedding": {"model_name": "test"},
                "schema": {"vector_size": 1024},
            }
        )
        pipeline = RetrievalPipeline(config)
        pipeline.hybrid = MagicMock()  # type: ignore[misc]
        pipeline.vector_store = MagicMock()  # type: ignore[misc]
        pipeline.reranker = MagicMock()  # type: ignore[misc]
        pipeline.expander = MagicMock()  # type: ignore[misc]
        pipeline.compressor = MagicMock()  # type: ignore[misc]
        return pipeline

    def _make_chunk(
        self,
        chunk_id: str = "c1",
        chunk_type: ChunkType = ChunkType.PARAGRAPH,
        content: str = "test",
        source_md: str = "doc.md",
        score: float = 0.9,
        parent_id: str | None = None,
    ) -> Chunk:
        return Chunk(
            id=chunk_id,
            content=content,
            chunk_type=chunk_type,
            source_md=source_md,
            score=score,
            parent_id=parent_id,
        )

    @pytest.mark.asyncio
    async def test_enrichment_not_truncated_by_top_k(
        self, pipeline: RetrievalPipeline
    ) -> None:
        """When top_k=3 and all 3 hits are edge chunks, document chunk should still appear."""
        hits = [
            self._make_chunk(
                "e1", ChunkType.PARAGRAPH, source_md="doc.md", score=0.9, parent_id="p1"
            ),
            self._make_chunk(
                "e2", ChunkType.PARAGRAPH, source_md="doc.md", score=0.85, parent_id="p1"
            ),
            self._make_chunk(
                "e3", ChunkType.PARAGRAPH, source_md="doc.md", score=0.8, parent_id="p1"
            ),
        ]
        parent = self._make_chunk("p1", ChunkType.SECTION, source_md="doc.md", score=0.5)
        doc_chunk = self._make_chunk("d1", ChunkType.DOCUMENT, source_md="doc.md", score=0.5)

        pipeline.hybrid.retrieve = MagicMock(return_value=hits)
        pipeline.vector_store.get_by_ids = MagicMock(return_value=[parent])
        pipeline.vector_store.scroll = MagicMock(return_value=([doc_chunk], None))

        planner = RetrievalPlanner(pipeline.config)
        plan = planner.plan("test query")

        results = await pipeline.search_enriched(query="test", plan=plan, top_k=3)

        ids = [c.id for c, _ in results]
        assert "e1" in ids
        assert "e2" in ids
        assert "e3" in ids
        # Enrichment chunks should be present (parent or document)
        assert "p1" in ids or "d1" in ids
        # Total should be at least top_k, but not unbounded
        assert len(results) <= 3 + 3  # top_k + enrichment_budget

    @pytest.mark.asyncio
    async def test_primary_hits_preserved_before_enrichment(
        self, pipeline: RetrievalPipeline
    ) -> None:
        """Primary hits should keep their relative ordering before enrichment chunks."""
        hits = [
            self._make_chunk("e1", ChunkType.PARAGRAPH, score=0.9, parent_id="p1"),
            self._make_chunk("e2", ChunkType.PARAGRAPH, score=0.85, parent_id="p1"),
        ]
        parent = self._make_chunk("p1", ChunkType.SECTION, score=0.5)

        pipeline.hybrid.retrieve = MagicMock(return_value=hits)
        pipeline.vector_store.get_by_ids = MagicMock(return_value=[parent])
        pipeline.vector_store.scroll = MagicMock(return_value=([], None))

        planner = RetrievalPlanner(pipeline.config)
        plan = planner.plan("test")

        results = await pipeline.search_enriched(query="test", plan=plan, top_k=2)

        ids = [c.id for c, _ in results]
        assert ids[0] == "e1"
        assert ids[1] == "e2"
        if len(ids) > 2:
            assert ids[2] == "p1"

    @pytest.mark.asyncio
    async def test_retrieve_enriched_uses_search_enriched(
        self, pipeline: RetrievalPipeline
    ) -> None:
        """retrieve_enriched should delegate to search_enriched for phase 1."""
        chunk = self._make_chunk("c1", score=0.9)

        pipeline.hybrid.retrieve = MagicMock(return_value=[chunk])
        pipeline.reranker.rerank = MagicMock(return_value=[chunk])
        pipeline.expander.expand = MagicMock(return_value=[chunk])
        pipeline.compressor.compress = MagicMock(return_value=[chunk])

        planner = RetrievalPlanner(pipeline.config)
        plan = planner.plan("test")

        results = await pipeline.retrieve_enriched(
            query="test",
            plan=plan,
            top_k=5,
            rerank=True,
            expand_parents=True,
            expand_siblings=False,
            compress=True,
        )

        assert len(results) == 1
        assert results[0][0].id == "c1"
        pipeline.reranker.rerank.assert_called_once()
        pipeline.expander.expand.assert_called_once()
        pipeline.compressor.compress.assert_called_once()
