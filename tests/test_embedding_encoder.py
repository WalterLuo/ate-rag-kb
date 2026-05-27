"""Unit tests for embedding encoder."""

from __future__ import annotations

import os
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

    def test_online_mode_does_not_force_offline_environment(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setenv("HF_HUB_OFFLINE", "1")
        monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
        cfg = Config(
            {
                "embedding": {
                    "device": "cpu",
                    "cache_dir": str(tmp_path),
                    "local_files_only": False,
                }
            }
        )

        with patch("ate_rag_kb.embedding.encoder.SentenceTransformer") as mock_cls:
            encoder = EmbeddingEncoder(cfg)
            _ = encoder.model

        assert "HF_HUB_OFFLINE" not in os.environ
        assert "TRANSFORMERS_OFFLINE" not in os.environ
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["local_files_only"] is False

    def test_offline_mode_raises_clear_error_when_cache_missing(self, tmp_path) -> None:
        cfg = Config(
            {
                "embedding": {
                    "model_name": "BAAI/bge-m3",
                    "device": "cpu",
                    "cache_dir": str(tmp_path),
                    "local_files_only": True,
                }
            }
        )
        encoder = EmbeddingEncoder(cfg)

        with pytest.raises(FileNotFoundError, match="Local model cache not found"):
            _ = encoder.model
