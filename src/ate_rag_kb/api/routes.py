"""API route definitions for ATE RAG Knowledge Base."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from ate_rag_kb.api.models import (
    AskRequest,
    AskResponse,
    ChunkResult,
    Citation,
    DocumentResponse,
    RelatedRequest,
    RelatedResponse,
    RetrieveRequest,
    RetrieveResponse,
    SearchRequest,
    SearchResponse,
)
from ate_rag_kb.chunking.models import Chunk

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Placeholder retrieval layer — replace with real vector store + pipeline
# ---------------------------------------------------------------------------

_retriever: Any | None = None


def set_retriever(retriever: Any) -> None:
    """Inject the retrieval backend (called during app creation)."""
    global _retriever
    _retriever = retriever


def _ensure_retriever() -> Any:
    if _retriever is None:
        raise HTTPException(status_code=503, detail="Retrieval backend not initialized")
    return _retriever


def _chunk_to_result(chunk: Chunk, score: float = 0.0) -> ChunkResult:
    """Convert internal Chunk model to API ChunkResult."""
    return ChunkResult(
        id=chunk.id,
        content=chunk.content,
        score=score,
        chunk_type=chunk.chunk_type.value,
        doc_title=chunk.doc_title,
        section_title=chunk.section_title,
        subsection_title=chunk.subsection_title,
        source_md=chunk.source_md,
        toc_path=chunk.toc_path,
        platform=chunk.platform,
        doc_type=chunk.doc_type,
        tags=chunk.tags,
        heading_level=chunk.heading_level,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        parent_id=chunk.parent_id,
        sibling_ids=chunk.sibling_ids,
        child_ids=chunk.child_ids,
        images=chunk.images,
        tables=chunk.tables,
        code_blocks=chunk.code_blocks,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """Semantic search over the ATE knowledge base."""
    retriever = _ensure_retriever()
    results: list[tuple[Chunk, float]] = await retriever.search(
        query=request.query,
        top_k=request.top_k,
        filters=request.filters,
    )
    chunks = [_chunk_to_result(chunk, score) for chunk, score in results]
    return SearchResponse(
        query=request.query,
        chunks=chunks,
        total=len(chunks),
    )


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    """Advanced retrieval with parent-child expansion, reranking, and compression."""
    retriever = _ensure_retriever()
    results: list[tuple[Chunk, float]] = await retriever.retrieve(
        query=request.query,
        top_k=request.top_k,
        filters=request.filters,
        expand_parents=request.expand_parents,
        expand_siblings=request.expand_siblings,
        rerank=request.rerank,
        compress=request.compress,
    )
    chunks = [_chunk_to_result(chunk, score) for chunk, score in results]
    return RetrieveResponse(
        query=request.query,
        chunks=chunks,
        total=len(chunks),
        reranked=request.rerank,
        expanded=request.expand_parents or request.expand_siblings,
        compressed=request.compress,
    )


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    """Agent-friendly Q&A endpoint with citations and source tracking."""
    retriever = _ensure_retriever()
    results: list[tuple[Chunk, float]] = await retriever.search(
        query=request.question,
        top_k=request.top_k,
        filters=request.filters,
    )

    chunks = [_chunk_to_result(chunk, score) for chunk, score in results]

    citations = [
        Citation(
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

    return AskResponse(
        question=request.question,
        chunks=chunks,
        citations=citations,
        toc_paths=[list(tp) for tp in toc_paths],
        source_files=list(source_files),
    )


@router.post("/related", response_model=RelatedResponse)
async def related(request: RelatedRequest) -> RelatedResponse:
    """Find related chunks (parent, siblings, children) for a given chunk."""
    retriever = _ensure_retriever()
    relations = await retriever.get_related(request.chunk_id)

    parent = None
    if relations.get("parent"):
        parent = _chunk_to_result(relations["parent"], score=1.0)

    siblings = [
        _chunk_to_result(chunk, score=1.0)
        for chunk in relations.get("siblings", [])
    ]
    children = [
        _chunk_to_result(chunk, score=1.0)
        for chunk in relations.get("children", [])
    ]

    return RelatedResponse(
        chunk_id=request.chunk_id,
        parent=parent,
        siblings=siblings,
        children=children,
    )


@router.get("/document/{source_md}", response_model=DocumentResponse)
async def get_document(source_md: str) -> DocumentResponse:
    """Return all chunks for a given markdown source file."""
    retriever = _ensure_retriever()
    chunks: list[Chunk] = await retriever.get_document(source_md)
    results = [_chunk_to_result(chunk, score=1.0) for chunk in chunks]
    return DocumentResponse(
        source_md=source_md,
        chunks=results,
        total=len(results),
    )
