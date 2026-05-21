"""Qdrant vector store client wrapper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, ScoredPoint

from ate_rag_kb.chunking.models import Chunk
from ate_rag_kb.utils.config import Config
from ate_rag_kb.vector_store.schema import build_filter, create_collection, ensure_collection

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Local-first Qdrant vector store for ATE KB chunks."""

    def __init__(self, config: Config | None = None) -> None:
        cfg = config or Config({})
        self.collection_name: str = cfg.get("vector_store.collection_name", "ate_kb")
        self.use_local: bool = cfg.get("vector_store.use_local", True)
        self.local_path: Path = Path(cfg.get("vector_store.local_path", "./data/qdrant_storage"))

        if self.use_local:
            self.local_path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(self.local_path))
            logger.info("Initialized local Qdrant at %s", self.local_path)
        else:
            host = cfg.get("vector_store.host", "localhost")
            port = cfg.get("vector_store.port", 6333)
            self.client = QdrantClient(host=host, port=port)
            logger.info("Initialized remote Qdrant at %s:%s", host, port)

        ensure_collection(self.client, cfg)

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        """Batch upsert chunks with embeddings into Qdrant."""
        if not chunks:
            return

        points: list[PointStruct] = []
        for chunk in chunks:
            if chunk.embedding is None:
                logger.warning("Chunk %s has no embedding; skipping.", chunk.id)
                continue
            points.append(
                PointStruct(
                    id=chunk.id,
                    vector=chunk.embedding,
                    payload={
                        **chunk.to_payload(),
                        "content": chunk.content,
                    },
                )
            )

        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info("Upserted %d chunks into '%s'.", len(points), self.collection_name)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Vector search returning Chunk objects."""
        qdrant_filter = build_filter(filters) if filters else None
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        return [
            Chunk.from_payload(r.id, {**(r.payload or {}), "score": r.score})
            for r in response.points
        ]

    def scroll(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: str | None = None,
    ) -> tuple[list[Chunk], str | None]:
        """List chunks with optional filtering."""
        qdrant_filter = build_filter(filters) if filters else None
        results, next_offset = self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            offset=offset,
            scroll_filter=qdrant_filter,
            with_payload=True,
        )
        chunks = [
            Chunk.from_payload(r.id, r.payload or {})
            for r in results
        ]
        return chunks, next_offset

    def delete_by_source(self, source_md: str) -> None:
        """Delete all chunks from a given markdown source file."""
        qdrant_filter = build_filter({"source_md": source_md})
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qdrant_filter,
        )
        logger.info("Deleted chunks for source: %s", source_md)

    def get_by_id(self, chunk_id: str) -> Chunk | None:
        """Fetch a single chunk by ID."""
        results = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[chunk_id],
            with_payload=True,
        )
        if results and results[0].payload:
            return Chunk.from_payload(results[0].id, results[0].payload)
        return None

    def count(self) -> int:
        """Return total number of points in the collection."""
        return self.client.count(collection_name=self.collection_name).count
