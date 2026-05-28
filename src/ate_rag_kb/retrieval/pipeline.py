"""Unified retrieval pipeline for the API layer."""

from __future__ import annotations

import asyncio
import logging
import typing
from typing import Any

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.embedding.encoder import EmbeddingEncoder
from ate_rag_kb.retrieval.compression import ContextCompressor
from ate_rag_kb.retrieval.hybrid import HybridRetriever
from ate_rag_kb.retrieval.parent_child import ParentChildExpander
from ate_rag_kb.retrieval.reranker import Reranker
from ate_rag_kb.utils.config import Config
from ate_rag_kb.vector_store.qdrant_client import QdrantVectorStore

if typing.TYPE_CHECKING:
    from ate_rag_kb.retrieval.planner import RetrievalPlan

logger = logging.getLogger(__name__)


class RetrievalPipeline:
    """High-level retrieval facade wiring hybrid search, reranking, expansion, and compression."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.encoder = EmbeddingEncoder(config)
        self.vector_store = QdrantVectorStore(config)
        self.hybrid = HybridRetriever(self.encoder, self.vector_store, config)
        self.reranker = Reranker(config)
        self.expander = ParentChildExpander(config)
        self.compressor = ContextCompressor(config)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Basic semantic search returning chunks with scores."""
        chunks: list[Chunk] = await asyncio.to_thread(
            self.hybrid.retrieve, query, top_k, filters
        )
        return [(c, c.score) for c in chunks]

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        expand_parents: bool = True,
        expand_siblings: bool = True,
        rerank: bool = True,
        compress: bool = True,
    ) -> list[tuple[Chunk, float]]:
        """Advanced retrieval with optional reranking, parent-child expansion, and compression."""
        chunks: list[Chunk] = await asyncio.to_thread(
            self.hybrid.retrieve, query, top_k, filters
        )

        if rerank:
            chunks = await asyncio.to_thread(self.reranker.rerank, query, chunks)

        if expand_parents or expand_siblings:
            chunks = await asyncio.to_thread(
                self.expander.expand,
                chunks,
                self.vector_store,
                include_parent=expand_parents,
                include_siblings=expand_siblings,
            )

        if compress:
            chunks = await asyncio.to_thread(self.compressor.compress, chunks)

        return [(c, c.score) for c in chunks]

    async def search_enriched(
        self,
        query: str,
        plan: RetrievalPlan,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Planner-driven search with title boost and context enrichment."""
        search_top_k = top_k * 3
        effective_filters = filters if filters is not None else plan.inferred_filters
        chunks: list[Chunk] = await asyncio.to_thread(
            self.hybrid.retrieve, plan.enhanced_query, search_top_k, effective_filters
        )

        # Title / TOC boost
        boost_factor = self.config.get("retrieval.planner.title_boost_factor", 0.15)
        chunks = self._boost_title_matches(chunks, plan.title_match_terms, boost_factor)

        # Context enrichment for edge chunks
        enrichment_enabled = self.config.get(
            "retrieval.planner.context_enrichment_enabled", True
        )
        primary = chunks[:top_k]
        if enrichment_enabled:
            enriched = await asyncio.to_thread(
                self._enrich_chunks, chunks[: top_k * 2]
            )
            primary_ids = {c.id for c in primary}
            enrichment_budget = self.config.get(
                "retrieval.planner.enrichment_budget", 3
            )
            enrichment_chunks = [
                c for c in enriched if c.id not in primary_ids
            ][:enrichment_budget]
            final_chunks = primary + enrichment_chunks
        else:
            final_chunks = primary

        return [(c, c.score) for c in final_chunks]

    async def retrieve_enriched(
        self,
        query: str,
        plan: RetrievalPlan,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        expand_parents: bool = True,
        expand_siblings: bool = True,
        rerank: bool = True,
        compress: bool = True,
    ) -> list[tuple[Chunk, float]]:
        """Advanced retrieval with planner-driven enrichment, title boost, and optional reranking/expansion/compression."""
        # Phase 1: enriched search with title boost and context enrichment
        chunks_with_scores = await self.search_enriched(
            query=query,
            plan=plan,
            top_k=top_k,
            filters=filters,
        )
        chunks = [c for c, _ in chunks_with_scores]

        # Phase 2: optional reranking
        if rerank:
            chunks = await asyncio.to_thread(self.reranker.rerank, query, chunks)

        # Phase 3: optional parent-child expansion
        if expand_parents or expand_siblings:
            chunks = await asyncio.to_thread(
                self.expander.expand,
                chunks,
                self.vector_store,
                include_parent=expand_parents,
                include_siblings=expand_siblings,
            )

        # Phase 4: optional compression
        if compress:
            chunks = await asyncio.to_thread(self.compressor.compress, chunks)

        return [(c, c.score) for c in chunks]

    @staticmethod
    def _boost_title_matches(
        chunks: list[Chunk],
        title_match_terms: list[str],
        boost_factor: float = 0.15,
    ) -> list[Chunk]:
        """Boost chunk scores based on title/TOC term matches."""
        if not title_match_terms:
            return chunks
        for chunk in chunks:
            haystack = " ".join(
                [
                    chunk.doc_title,
                    chunk.section_title,
                    chunk.subsection_title,
                    *chunk.toc_path,
                ]
            ).lower()
            match_count = sum(
                1 for term in title_match_terms if term.lower() in haystack
            )
            if match_count > 0:
                chunk.score *= 1.0 + boost_factor * match_count
        chunks.sort(key=lambda c: c.score, reverse=True)
        return chunks

    def _enrich_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Supplement edge chunks with parent and document context."""
        if not chunks:
            return chunks

        result_ids = {c.id for c in chunks}
        ordered = list(chunks)

        # Collect parent_ids from edge chunks
        parent_ids: list[str] = []
        source_mds_with_docs: set[str] = set()
        source_mds_needing_doc: set[str] = set()

        for chunk in chunks:
            if chunk.chunk_type not in (ChunkType.DOCUMENT, ChunkType.SECTION):
                if chunk.parent_id:
                    parent_ids.append(chunk.parent_id)
                if chunk.source_md:
                    source_mds_needing_doc.add(chunk.source_md)
            else:
                if chunk.source_md:
                    source_mds_with_docs.add(chunk.source_md)

        # Batch fetch parents
        if parent_ids:
            fetched = self.vector_store.get_by_ids(list(dict.fromkeys(parent_ids)))
            for parent in fetched:
                if parent is not None and parent.id not in result_ids:
                    ordered.append(parent)
                    result_ids.add(parent.id)

        # Fetch document chunks for sources that lack one
        for source_md in source_mds_needing_doc - source_mds_with_docs:
            try:
                doc_chunks, _ = self.vector_store.scroll(
                    filters={"source_md": source_md, "chunk_type": ChunkType.DOCUMENT.value},
                    limit=1,
                )
                for doc_chunk in doc_chunks:
                    if doc_chunk.id not in result_ids:
                        doc_chunk.score = 0.5
                        ordered.append(doc_chunk)
                        result_ids.add(doc_chunk.id)
            except Exception:
                logger.debug("Failed to fetch document chunk for %s", source_md)

        return ordered

    async def get_related(self, chunk_id: str) -> dict[str, Any]:
        """Fetch parent, siblings, and children for a chunk."""
        chunk = await asyncio.to_thread(self.vector_store.get_by_id, chunk_id)
        if chunk is None:
            return {"parent": None, "siblings": [], "children": []}

        parent = None
        if chunk.parent_id:
            parent = await asyncio.to_thread(self.vector_store.get_by_id, chunk.parent_id)

        siblings: list[Chunk] = []
        for sid in chunk.sibling_ids:
            sc = await asyncio.to_thread(self.vector_store.get_by_id, sid)
            if sc:
                siblings.append(sc)

        children: list[Chunk] = []
        for cid in chunk.child_ids:
            cc = await asyncio.to_thread(self.vector_store.get_by_id, cid)
            if cc:
                children.append(cc)

        return {"parent": parent, "siblings": siblings, "children": children}

    async def get_document(self, source_md: str) -> list[Chunk]:
        """Return all chunks belonging to a source markdown file."""
        all_chunks: list[Chunk] = []
        offset: str | None = None
        while True:
            chunks, next_offset = await asyncio.to_thread(
                self.vector_store.scroll,
                filters={"source_md": source_md},
                limit=100,
                offset=offset,
            )
            all_chunks.extend(chunks)
            if not next_offset:
                break
            offset = next_offset
        return all_chunks

    async def get_document_page(
        self,
        source_md: str,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return one numeric page of chunks for a source markdown file."""
        filters = {"source_md": source_md}
        total = await asyncio.to_thread(self.vector_store.count, filters)
        target_count = max(0, offset) + max(1, limit) + 1

        fetched: list[Chunk] = []
        qdrant_offset: str | None = None
        while len(fetched) < target_count:
            batch_limit = min(100, target_count - len(fetched))
            chunks, next_offset = await asyncio.to_thread(
                self.vector_store.scroll,
                filters=filters,
                limit=batch_limit,
                offset=qdrant_offset,
            )
            fetched.extend(chunks)
            if not next_offset or not chunks:
                break
            qdrant_offset = next_offset

        page_chunks = fetched[offset:offset + limit]
        has_more = offset + len(page_chunks) < total
        next_numeric_offset = offset + len(page_chunks) if has_more else None

        return {
            "chunks": page_chunks,
            "total": total,
            "returned": len(page_chunks),
            "has_more": has_more,
            "next_offset": next_numeric_offset,
        }

    async def collection_stats(self) -> dict[str, Any]:
        """Return collection statistics."""
        count = await asyncio.to_thread(self.vector_store.count)
        vector_size = self.config.get("schema.vector_size", 0)
        embedding_model = self.config.get("embedding.model_name", "")

        platforms: set[str] = set()
        doc_types: set[str] = set()
        sample_limit = 1000
        sample_chunks: list[Chunk] = []
        try:
            sample_chunks, _ = await asyncio.to_thread(
                self.vector_store.scroll, limit=sample_limit
            )
            for chunk in sample_chunks:
                if chunk.platform:
                    platforms.add(chunk.platform)
                if chunk.doc_type:
                    doc_types.add(chunk.doc_type)
        except Exception:
            logger.exception("Failed to sample platforms/doc_types for stats")

        return {
            "collection_name": self.vector_store.collection_name,
            "total_chunks": count,
            "vector_size": vector_size,
            "embedding_model": embedding_model,
            "platforms": sorted(platforms),
            "doc_types": sorted(doc_types),
            "sampled_chunks": len(sample_chunks),
        }
