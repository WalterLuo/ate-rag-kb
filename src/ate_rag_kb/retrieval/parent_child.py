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
        """Expand chunks with related context."""
        result_ids: set[str] = set()
        ordered: list[Chunk] = []

        for chunk in chunks:
            if chunk.id not in result_ids:
                ordered.append(chunk)
                result_ids.add(chunk.id)

            if self.include_parent and chunk.parent_id:
                parent = vector_store.get_by_id(chunk.parent_id)
                if parent and parent.id not in result_ids:
                    ordered.append(parent)
                    result_ids.add(parent.id)

            if self.include_siblings:
                for sid in chunk.sibling_ids[:self.max_siblings]:
                    if sid not in result_ids:
                        sibling = vector_store.get_by_id(sid)
                        if sibling:
                            ordered.append(sibling)
                            result_ids.add(sid)

            if self.include_children:
                for cid in chunk.child_ids:
                    if cid not in result_ids:
                        child = vector_store.get_by_id(cid)
                        if child:
                            ordered.append(child)
                            result_ids.add(cid)

        return ordered
