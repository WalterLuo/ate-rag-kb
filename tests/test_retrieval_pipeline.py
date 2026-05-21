"""Unit tests for retrieval pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.retrieval.pipeline import RetrievalPipeline
from ate_rag_kb.utils.config import Config


class TestRetrievalPipeline:
    @pytest.fixture
    def pipeline(self) -> RetrievalPipeline:
        cfg = Config({})
        with patch("ate_rag_kb.retrieval.pipeline.EmbeddingEncoder"):
            with patch("ate_rag_kb.retrieval.pipeline.QdrantVectorStore") as mock_vs:
                with patch("ate_rag_kb.retrieval.pipeline.HybridRetriever"):
                    with patch("ate_rag_kb.retrieval.pipeline.Reranker"):
                        with patch("ate_rag_kb.retrieval.pipeline.ParentChildExpander"):
                            with patch("ate_rag_kb.retrieval.pipeline.ContextCompressor"):
                                p = RetrievalPipeline(cfg)
                                p.vector_store = mock_vs.return_value
                                yield p

    @pytest.mark.asyncio
    async def test_search(self, pipeline: RetrievalPipeline) -> None:
        chunk = Chunk(id="c1", content="hello", chunk_type=ChunkType.PARAGRAPH, score=0.9)
        pipeline.hybrid.retrieve = MagicMock(return_value=[chunk])
        results = await pipeline.search("query", top_k=1)
        assert len(results) == 1
        assert results[0][1] == 0.9

    @pytest.mark.asyncio
    async def test_retrieve_with_rerank_expand_compress(self, pipeline: RetrievalPipeline) -> None:
        chunk = Chunk(id="c1", content="hello", chunk_type=ChunkType.PARAGRAPH, score=0.8)
        pipeline.hybrid.retrieve = MagicMock(return_value=[chunk])
        pipeline.reranker.rerank = MagicMock(return_value=[chunk])
        pipeline.expander.expand = MagicMock(return_value=[chunk])
        pipeline.compressor.compress = MagicMock(return_value=[chunk])
        results = await pipeline.retrieve("query", top_k=1)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_retrieve_without_options(self, pipeline: RetrievalPipeline) -> None:
        chunk = Chunk(id="c1", content="hello", chunk_type=ChunkType.PARAGRAPH, score=0.8)
        pipeline.hybrid.retrieve = MagicMock(return_value=[chunk])
        results = await pipeline.retrieve("query", top_k=1, rerank=False, expand_parents=False, expand_siblings=False, compress=False)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_related(self, pipeline: RetrievalPipeline) -> None:
        parent = Chunk(id="p1", content="parent", chunk_type=ChunkType.SECTION)
        child = Chunk(id="c1", content="child", chunk_type=ChunkType.PARAGRAPH, parent_id="p1", sibling_ids=["s1"])
        sibling = Chunk(id="s1", content="sibling", chunk_type=ChunkType.PARAGRAPH)
        pipeline.vector_store.get_by_id = MagicMock(side_effect=lambda x: {"p1": parent, "c1": child, "s1": sibling}.get(x))
        related = await pipeline.get_related("c1")
        assert related["parent"] == parent
        assert len(related["siblings"]) == 1

    @pytest.mark.asyncio
    async def test_get_related_missing_chunk(self, pipeline: RetrievalPipeline) -> None:
        pipeline.vector_store.get_by_id = MagicMock(return_value=None)
        related = await pipeline.get_related("missing")
        assert related["parent"] is None
        assert related["siblings"] == []

    @pytest.mark.asyncio
    async def test_get_document(self, pipeline: RetrievalPipeline) -> None:
        chunk = Chunk(id="c1", content="hello", chunk_type=ChunkType.PARAGRAPH)
        pipeline.vector_store.scroll = MagicMock(return_value=([chunk], None))
        docs = await pipeline.get_document("doc.md")
        assert len(docs) == 1

    @pytest.mark.asyncio
    async def test_get_document_paginates(self, pipeline: RetrievalPipeline) -> None:
        c1 = Chunk(id="c1", content="a", chunk_type=ChunkType.PARAGRAPH)
        c2 = Chunk(id="c2", content="b", chunk_type=ChunkType.PARAGRAPH)
        pipeline.vector_store.scroll = MagicMock(side_effect=[
            ([c1], "offset1"),
            ([c2], None),
        ])
        docs = await pipeline.get_document("doc.md")
        assert len(docs) == 2

    @pytest.mark.asyncio
    async def test_collection_stats(self, pipeline: RetrievalPipeline) -> None:
        pipeline.vector_store.count = MagicMock(return_value=42)
        pipeline.vector_store.collection_name = "test"
        stats = await pipeline.collection_stats()
        assert stats["total_chunks"] == 42
        assert stats["collection_name"] == "test"
