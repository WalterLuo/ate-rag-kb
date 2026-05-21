"""Qdrant collection schema setup."""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    VectorParams,
)

logger = logging.getLogger(__name__)


def create_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int = 1024,
    distance: Distance = Distance.COSINE,
) -> None:
    """Create a Qdrant collection if it does not exist."""
    collections = client.get_collections().collections
    existing = [c.name for c in collections]
    if collection_name in existing:
        logger.info("Collection '%s' already exists.", collection_name)
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=distance),
    )
    logger.info("Created collection '%s' with vector_size=%d.", collection_name, vector_size)


def create_payload_indexes(
    client: QdrantClient,
    collection_name: str,
    fields: dict[str, str] | None = None,
) -> None:
    """Create payload indexes for metadata filtering."""
    if fields is None:
        fields = {
            "platform": "keyword",
            "doc_type": "keyword",
            "chunk_type": "keyword",
            "source_md": "text",
            "doc_title": "text",
        }

    for field_name, field_type in fields.items():
        schema_type = (
            PayloadSchemaType.KEYWORD
            if field_type == "keyword"
            else PayloadSchemaType.TEXT
        )
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema_type,
            )
            logger.info("Created %s index on '%s'.", field_type, field_name)
        except Exception as exc:
            logger.warning("Index on '%s' may already exist: %s", field_name, exc)


def ensure_collection(client: QdrantClient, config: Any) -> None:
    """Idempotent collection + index setup."""
    collection_name = config.get("vector_store.collection_name", "ate_kb")
    vector_size = config.get("schema.vector_size", 1024)
    distance_str = config.get("schema.distance", "Cosine")
    distance = getattr(Distance, distance_str.upper(), Distance.COSINE)

    create_collection(client, collection_name, vector_size, distance)

    indexes = config.get("schema.payload_indexes", [])
    fields = {idx["field"]: idx["type"] for idx in indexes}
    create_payload_indexes(client, collection_name, fields)


def build_filter(filters: dict[str, Any]) -> Filter | None:
    """Build a Qdrant Filter from a dict of field->value mappings."""
    if not filters:
        return None
    conditions = []
    for field, value in filters.items():
        if isinstance(value, list):
            conditions.append(FieldCondition(key=field, match=MatchAny(any=value)))
        else:
            conditions.append(FieldCondition(key=field, match=MatchValue(value=value)))
    return Filter(must=conditions) if conditions else None
