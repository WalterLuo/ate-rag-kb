"""MCP tool definitions and handlers for ATE RAG Knowledge Base.

Each tool reuses the existing RetrievalPipeline and returns structured
JSON that agents can consume directly.
"""

from __future__ import annotations

import logging
from typing import Any

from ate_rag_kb.chunking.models import Chunk
from ate_rag_kb.mcp.context_builder import (
    _chunk_to_mcp,
    build_context_package,
    build_sources_summary,
    compute_confidence,
)
from ate_rag_kb.mcp.models import (
    McpAskResult,
    McpCitation,
    McpDocumentResult,
    McpRelatedResult,
    McpRetrieveResult,
    McpSearchResult,
    McpStatusResult,
)
from ate_rag_kb.retrieval.pipeline import RetrievalPipeline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas (JSON Schema for MCP discovery)
# ---------------------------------------------------------------------------

_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "Search query. Use natural language, not keywords. "
                "Example: 'How to configure drive edge in timing set'"
            ),
        },
        "top_k": {
            "type": "integer",
            "default": 10,
            "minimum": 1,
            "maximum": 50,
            "description": "Maximum number of chunks to return",
        },
        "filters": {
            "type": "object",
            "default": {},
            "description": (
                "Optional metadata filters. Supported: platform, doc_type, chunk_type, tags"
            ),
        },
    },
    "required": ["query"],
}

_RETRIEVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query in natural language",
        },
        "top_k": {
            "type": "integer",
            "default": 10,
            "minimum": 1,
            "maximum": 50,
            "description": "Number of results after all processing",
        },
        "filters": {
            "type": "object",
            "default": {},
            "description": "Same filter schema as ate_kb.search",
        },
        "rerank": {
            "type": "boolean",
            "default": True,
            "description": "Apply cross-encoder reranking (slower, more accurate)",
        },
        "expand_parents": {
            "type": "boolean",
            "default": True,
            "description": "Include parent section chunks for context",
        },
        "expand_siblings": {
            "type": "boolean",
            "default": True,
            "description": "Include sibling chunks (adjacent sections)",
        },
        "compress": {
            "type": "boolean",
            "default": True,
            "description": "Merge adjacent chunks and remove duplicates",
        },
        "max_tokens": {
            "type": "integer",
            "default": 4000,
            "minimum": 500,
            "maximum": 16000,
            "description": "Approximate token budget for returned content",
        },
    },
    "required": ["query"],
}

_ASK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "The question to answer",
        },
        "top_k": {
            "type": "integer",
            "default": 8,
            "minimum": 1,
            "maximum": 50,
        },
        "filters": {
            "type": "object",
            "default": {},
            "description": "Same filter schema as ate_kb.search",
        },
        "include_context_package": {
            "type": "boolean",
            "default": True,
            "description": "Include full context package for agent's own reasoning",
        },
    },
    "required": ["question"],
}

_RELATED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "chunk_id": {
            "type": "string",
            "description": "The chunk ID to find relations for",
        },
        "include_parent": {
            "type": "boolean",
            "default": True,
        },
        "include_siblings": {
            "type": "boolean",
            "default": True,
        },
        "include_children": {
            "type": "boolean",
            "default": False,
        },
        "max_siblings": {
            "type": "integer",
            "default": 2,
            "minimum": 0,
            "maximum": 10,
        },
    },
    "required": ["chunk_id"],
}

_GET_DOCUMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "source_md": {
            "type": "string",
            "description": "Source markdown file name (e.g., '118727.md')",
        },
    },
    "required": ["source_md"],
}

_STATUS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
}

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "ate_kb.search": _SEARCH_SCHEMA,
    "ate_kb.retrieve": _RETRIEVE_SCHEMA,
    "ate_kb.ask": _ASK_SCHEMA,
    "ate_kb.related": _RELATED_SCHEMA,
    "ate_kb.get_document": _GET_DOCUMENT_SCHEMA,
    "ate_kb.status": _STATUS_SCHEMA,
}

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class McpToolHandler:
    """Wraps RetrievalPipeline methods as MCP tool handlers."""

    def __init__(self, pipeline: RetrievalPipeline) -> None:
        self.pipeline = pipeline

    async def handle_search(self, args: dict[str, Any]) -> McpSearchResult:
        """Handle ate_kb.search."""
        query = args["query"]
        top_k = args.get("top_k", 10)
        filters = args.get("filters") or None

        results: list[tuple[Chunk, float]] = await self.pipeline.search(
            query=query,
            top_k=top_k,
            filters=filters,
        )
        chunks = [_chunk_to_mcp(chunk, score) for chunk, score in results]
        sources = build_sources_summary(chunks)

        return McpSearchResult(
            query=query,
            total=len(chunks),
            chunks=chunks,
            sources=sources,
        )

    async def handle_retrieve(self, args: dict[str, Any]) -> McpRetrieveResult:
        """Handle ate_kb.retrieve."""
        query = args["query"]
        top_k = args.get("top_k", 10)
        filters = args.get("filters") or None
        rerank = args.get("rerank", True)
        expand_parents = args.get("expand_parents", True)
        expand_siblings = args.get("expand_siblings", True)
        compress = args.get("compress", True)
        max_tokens = args.get("max_tokens", 4000)

        results: list[tuple[Chunk, float]] = await self.pipeline.retrieve(
            query=query,
            top_k=top_k,
            filters=filters,
            expand_parents=expand_parents,
            expand_siblings=expand_siblings,
            rerank=rerank,
            compress=compress,
        )
        chunks = [_chunk_to_mcp(chunk, score) for chunk, score in results]
        context_package = build_context_package(results, max_tokens=max_tokens)

        return McpRetrieveResult(
            query=query,
            total=len(chunks),
            processing={
                "reranked": rerank,
                "expanded": expand_parents or expand_siblings,
                "compressed": compress,
                "vector_candidates": len(results),
            },
            chunks=chunks,
            context_package=context_package,
        )

    async def handle_ask(self, args: dict[str, Any]) -> McpAskResult:
        """Handle ate_kb.ask.

        Phase 1: No LLM synthesis. Returns grounded context package + citations.
        """
        question = args["question"]
        top_k = args.get("top_k", 8)
        filters = args.get("filters") or None
        include_context = args.get("include_context_package", True)

        results: list[tuple[Chunk, float]] = await self.pipeline.search(
            query=question,
            top_k=top_k,
            filters=filters,
        )
        chunks = [_chunk_to_mcp(chunk, score) for chunk, score in results]

        citations = [
            McpCitation(
                chunk_id=chunk.id,
                excerpt=chunk.content[:300],
                source_md=chunk.source_md,
                toc_path=chunk.toc_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            )
            for chunk in chunks
        ]

        toc_paths = sorted({tuple(c.toc_path) for c in chunks if c.toc_path})
        source_files = sorted({c.source_md for c in chunks if c.source_md})
        confidence = compute_confidence(chunks)

        context_package = None
        if include_context:
            context_package = build_context_package(results)

        return McpAskResult(
            question=question,
            answer=(
                "Use the provided context package and citations to synthesize an answer. "
                "Always cite source_md and section_title for every claim."
            ),
            citations=citations,
            source_files=list(source_files),
            toc_paths=[list(tp) for tp in toc_paths],
            confidence=confidence,
            context_package=context_package,
        )

    async def handle_related(self, args: dict[str, Any]) -> McpRelatedResult:
        """Handle ate_kb.related."""
        chunk_id = args["chunk_id"]
        include_parent = args.get("include_parent", True)
        include_siblings = args.get("include_siblings", True)
        include_children = args.get("include_children", False)

        relations = await self.pipeline.get_related(chunk_id)

        parent = None
        if include_parent and relations.get("parent"):
            parent = _chunk_to_mcp(relations["parent"], score=1.0)

        siblings = [
            _chunk_to_mcp(chunk, score=1.0)
            for chunk in relations.get("siblings", [])
            if include_siblings
        ]
        children = [
            _chunk_to_mcp(chunk, score=1.0)
            for chunk in relations.get("children", [])
            if include_children
        ]

        return McpRelatedResult(
            chunk_id=chunk_id,
            parent=parent,
            siblings=siblings,
            children=children,
        )

    async def handle_get_document(self, args: dict[str, Any]) -> McpDocumentResult:
        """Handle ate_kb.get_document."""
        source_md = args["source_md"]
        chunks = await self.pipeline.get_document(source_md)
        results = [_chunk_to_mcp(chunk, score=1.0) for chunk in chunks]

        return McpDocumentResult(
            source_md=source_md,
            total=len(results),
            chunks=results,
        )

    async def handle_status(self, _args: dict[str, Any]) -> McpStatusResult:
        """Handle ate_kb.status."""
        try:
            stats = await self.pipeline.collection_stats()
            return McpStatusResult(
                status="ok",
                collection_name=stats.get("collection_name", ""),
                total_chunks=stats.get("total_chunks", 0),
                vector_size=stats.get("vector_size", 0),
                embedding_model=stats.get("embedding_model", ""),
                platforms=stats.get("platforms", []),
                doc_types=stats.get("doc_types", []),
                version="0.1.0",
            )
        except Exception as exc:
            logger.error("Status check failed: %s", exc)
            return McpStatusResult(status="degraded")
