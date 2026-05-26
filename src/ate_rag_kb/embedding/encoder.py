"""Embedding encoder using sentence-transformers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

# Force offline mode before any huggingface/transformers imports to prevent
# network requests when local model cache is available.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ.pop("HF_ENDPOINT", None)

import numpy as np
from sentence_transformers import SentenceTransformer

from ate_rag_kb.utils.config import Config

logger = logging.getLogger(__name__)


class EmbeddingEncoder:
    """Wrapper around sentence-transformers for ATE KB embeddings."""

    def __init__(self, config: Config | None = None, device: str | None = None) -> None:
        cfg = config or Config({})
        self.model_name: str = cfg.get("embedding.model_name", "BAAI/bge-m3")
        requested_device = device or cfg.get("embedding.device", "auto")
        self.device: str = self._resolve_device(requested_device)
        self.normalize: bool = cfg.get("embedding.normalize_embeddings", True)
        self.batch_size: int = cfg.get("embedding.batch_size", 32)
        self.max_seq_length: int = cfg.get("embedding.max_seq_length", 8192)
        self.cache_dir: Path = Path(cfg.get("embedding.cache_dir", "./embeddings/cache"))
        self.local_files_only: bool = cfg.get("embedding.local_files_only", True)
        self.query_instruction: str = cfg.get(
            "embedding.query_instruction",
            "Represent this sentence for searching relevant passages: ",
        )
        self._model: SentenceTransformer | None = None

    def _resolve_device(self, device: str) -> str:
        if device != "auto":
            return device
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _resolve_local_model_path(self) -> str:
        """Resolve a huggingface_hub cache entry to a local snapshot path.

        When local_files_only is true, SentenceTransformer may still attempt
        network calls to validate missing safetensors files. Loading directly
        from the cached snapshot path bypasses those checks entirely.
        """
        if not self.local_files_only:
            return self.model_name

        # huggingface_hub cache layout:
        #   cache_dir/models--{org}--{model}/snapshots/{commit_hash}/
        safe_name = self.model_name.replace("/", "--")
        cache_entry = self.cache_dir / f"models--{safe_name}"
        snapshots_dir = cache_entry / "snapshots"

        if not snapshots_dir.exists():
            logger.warning(
                "No local cache found for %s at %s; falling back to model name",
                self.model_name,
                cache_entry,
            )
            return self.model_name

        # Pick the first snapshot that contains a config.json (valid model)
        for snapshot in snapshots_dir.iterdir():
            if snapshot.is_dir() and (snapshot / "config.json").exists():
                logger.info("Using local snapshot: %s", snapshot)
                return str(snapshot)

        logger.warning(
            "No valid snapshot found for %s; falling back to model name", self.model_name
        )
        return self.model_name

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model: %s on %s", self.model_name, self.device)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            model_path = self._resolve_local_model_path()
            self._model = SentenceTransformer(
                model_path,
                device=self.device,
                cache_folder=str(self.cache_dir),
                local_files_only=self.local_files_only,
            )
            self._model.max_seq_length = self.max_seq_length
        return self._model

    def encode(self, texts: list[str], batch_size: int | None = None) -> np.ndarray:
        """Encode a list of texts into normalized embeddings."""
        if not texts:
            return np.array([])
        bs = batch_size or self.batch_size
        embeddings = self.model.encode(
            texts,
            batch_size=bs,
            normalize_embeddings=self.normalize,
            show_progress_bar=len(texts) > 100,
        )
        return np.asarray(embeddings)

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a query with instruction prefix."""
        text = self.query_instruction + query
        return self.encode([text])[0]

    def encode_documents(self, documents: list[str]) -> np.ndarray:
        """Encode documents (passages)."""
        return self.encode(documents)

    @property
    def vector_size(self) -> int:
        return self.model.get_sentence_embedding_dimension()
