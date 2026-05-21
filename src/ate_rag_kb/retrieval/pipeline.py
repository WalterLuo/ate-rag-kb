"""Unified retrieval pipeline for the API layer."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ate_rag_kb.chunking.models import Chunk
from ate_rag_kb.embedding.encoder import EmbeddingEncoder
from ate_rag_kb.retrieval.compression import ContextCompressor
from ate_rag_kb.retrieval.hybrid import HybridRetriever
from ate_rag_kb.retrieval.parent_child import ParentChildExpander
from ate_rag_kb.retrieval.reranker import Reranker
from ate_rag_kb.utils.config import Config
from ate_rag_kb.vector_store.qdrant_client import QdrantVectorStore

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
            original_parent = self.expander.include_parent
            original_siblings = self.expander.include_siblings
            self.expander.include_parent = expand_parents
            self.expander.include_siblings = expand_siblings
            try:
                chunks = await asyncio.to_thread(
                    self.expander.expand, chunks, self.vector_store
                )
            finally:
                self.expander.include_parent = original_parent
                self.expander.include_siblings = original_siblings

        if compress:
            chunks = await asyncio.to_thread(self.compressor.compress, chunks)

        return [(c, c.score) for c in chunks]

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

    async def collection_stats(self) -> dict[str, Any]:
        """Return collection statistics."""
        count = await asyncio.to_thread(self.vector_store.count)
        return {
            "collection_name": self.vector_store.collection_name,
            "total_chunks": count,
        }
