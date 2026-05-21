"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ate_rag_kb.api.routes import router, set_retriever
from ate_rag_kb.utils.config import Config

logger = logging.getLogger(__name__)


def create_app(config: Config) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ATE RAG Knowledge Base",
        description="Agentic RAG API for ATE Test Engineer documentation.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Include API routes
    app.include_router(router, prefix="/api/v1")

    # Lifecycle: inject retriever backend if available
    @app.on_event("startup")
    async def _startup() -> None:
        retriever = _build_retriever(config)
        if retriever is not None:
            set_retriever(retriever)
            logger.info("Retriever backend initialized")

    return app


def _build_retriever(config: Config) -> object | None:
    """Attempt to build the retriever from config."""
    try:
        # Deferred import to avoid heavy startup cost when retriever is not yet implemented
        from ate_rag_kb.retrieval.pipeline import RetrievalPipeline

        return RetrievalPipeline(config)
    except Exception:
        logger.warning("Retriever backend not available; API will return 503")
        return None
