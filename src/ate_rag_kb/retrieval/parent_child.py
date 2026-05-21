"""Parent-child chunk expansion for context enrichment."""

from __future__ import annotations

import logging
from typing import Any

from ate_rag_kb.chunking.models import Chunk
from ate_rag_kb.utils.config import Config
from ate_rag_kb.vector_store.qdrant_client import QdrantVectorStore

logger = logging.getLogger(__name__)


class ParentChildExpander:
    """Expand retrieved chunks with parent, sibling, and child context."""

    def __init__(self, config: Config | None = None) -> None:
        cfg = config or Config({})
        self.include_parent = cfg.get("retrieval.parent_child.include_parent", True)
        self.include_siblings = cfg.get("retrieval.parent_child.include_siblings", True)
        self.include_children = cfg.get("retrieval.parent_child.include_children", False)
        self.max_siblings = cfg.get("retrieval.parent_child.max_siblings", 2)

    def expand(
        self,
        chunks: list[Chunk],
        vector_store: QdrantVectorStore,
    ) -> list[Chunk]:
        """Expand chunks with related context using batched fetches."""
        result_ids: set[str] = set()
        ordered: list[Chunk] = []

        # First pass: add original chunks and collect related IDs
        parent_ids: list[str] = []
        sibling_ids: list[str] = []
        child_ids: list[str] = []

        for chunk in chunks:
            if chunk.id not in result_ids:
                ordered.append(chunk)
                result_ids.add(chunk.id)
            if self.include_parent and chunk.parent_id:
                parent_ids.append(chunk.parent_id)
            if self.include_siblings:
                sibling_ids.extend(chunk.sibling_ids[:self.max_siblings])
            if self.include_children:
                child_ids.extend(chunk.child_ids)

        # Batch fetch all related chunks in a single round-trip per type
        id_to_chunk: dict[str, Chunk] = {}
        all_related_ids = list(dict.fromkeys(parent_ids + sibling_ids + child_ids))
        if all_related_ids:
            fetched = vector_store.get_by_ids(all_related_ids)
            for cid, chunk in zip(all_related_ids, fetched):
                if chunk is not None:
                    id_to_chunk[cid] = chunk

        # Second pass: append related chunks in original order
        for chunk in chunks:
            if self.include_parent and chunk.parent_id and chunk.parent_id in id_to_chunk:
                parent = id_to_chunk[chunk.parent_id]
                if parent.id not in result_ids:
                    ordered.append(parent)
                    result_ids.add(parent.id)

            if self.include_siblings:
                for sid in chunk.sibling_ids[:self.max_siblings]:
                    if sid in id_to_chunk and sid not in result_ids:
                        ordered.append(id_to_chunk[sid])
                        result_ids.add(sid)

            if self.include_children:
                for cid in chunk.child_ids:
                    if cid in id_to_chunk and cid not in result_ids:
                        ordered.append(id_to_chunk[cid])
                        result_ids.add(cid)

        return ordered
