"""Unit tests for embedding encoder."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from ate_rag_kb.embedding.encoder import EmbeddingEncoder
from ate_rag_kb.utils.config import Config


class TestEmbeddingEncoder:
    @pytest.fixture
    def encoder(self) -> EmbeddingEncoder:
        cfg = Config({"embedding": {"device": "cpu"}})
        with patch("ate_rag_kb.embedding.encoder.SentenceTransformer"):
            yield EmbeddingEncoder(cfg)

    def test_default_config(self, encoder: EmbeddingEncoder) -> None:
        assert encoder.model_name == "BAAI/bge-m3"
        assert encoder.batch_size == 32
        assert encoder.device == "cpu"

    def test_resolve_device_explicit(self, encoder: EmbeddingEncoder) -> None:
        assert encoder._resolve_device("cuda") == "cuda"

    def test_encode_empty_list(self, encoder: EmbeddingEncoder) -> None:
        result = encoder.encode([])
        assert result.size == 0

    def test_encode_query(self, encoder: EmbeddingEncoder) -> None:
        encoder.model.encode.return_value = np.array([[0.1, 0.2]])
        emb = encoder.encode_query("test")
        assert isinstance(emb, np.ndarray)
        assert emb.shape == (2,)

    def test_encode_documents(self, encoder: EmbeddingEncoder) -> None:
        encoder.model.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
        emb = encoder.encode_documents(["a", "b"])
        assert emb.shape == (2, 2)

    def test_vector_size(self, encoder: EmbeddingEncoder) -> None:
        encoder.model.get_sentence_embedding_dimension.return_value = 1024
        assert encoder.vector_size == 1024
