"""Unit tests for cross-encoder reranker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ate_rag_kb.chunking.models import Chunk, ChunkType
from ate_rag_kb.retrieval.reranker import Reranker
from ate_rag_kb.utils.config import Config


class TestReranker:
    def test_rerank_returns_top_k(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            model = MagicMock()
            model.predict.return_value = [0.5, 0.9, 0.1]
            mock_cls.return_value = model

            reranker = Reranker()
            chunks = [
                Chunk(id="c1", content="low", chunk_type=ChunkType.PARAGRAPH),
                Chunk(id="c2", content="high", chunk_type=ChunkType.PARAGRAPH),
                Chunk(id="c3", content="lower", chunk_type=ChunkType.PARAGRAPH),
            ]

            result = reranker.rerank("query", chunks, top_k=2)

            assert len(result) == 2
            assert result[0].id == "c2"

    def test_rerank_empty_list(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder"):
            reranker = Reranker()

            result = reranker.rerank("query", [])

            assert result == []

    def test_rerank_uses_default_top_k(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            model = MagicMock()
            model.predict.return_value = [0.1] * 10
            mock_cls.return_value = model

            reranker = Reranker()
            reranker.top_k = 3
            chunks = [
                Chunk(id=f"c{i}", content=f"text{i}", chunk_type=ChunkType.PARAGRAPH)
                for i in range(10)
            ]

            result = reranker.rerank("query", chunks)

            assert len(result) == 3

    def test_offline_mode_raises_clear_error_when_reranker_cache_missing(self, tmp_path) -> None:
        cfg = Config(
            {
                "embedding": {
                    "cache_dir": str(tmp_path),
                    "local_files_only": True,
                },
                "retrieval": {
                    "reranker": {
                        "model_name": "BAAI/bge-reranker-v2-m3",
                    }
                },
            }
        )
        reranker = Reranker(cfg)

        with pytest.raises(FileNotFoundError, match="Local model cache not found"):
            _ = reranker.model

    def test_reranker_cpu_device_passed_to_cross_encoder(self, tmp_path) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            cfg = Config(
                {
                    "embedding": {"cache_dir": str(tmp_path), "local_files_only": False},
                    "retrieval": {"reranker": {"device": "cpu"}},
                }
            )
            reranker = Reranker(cfg)
            _ = reranker.model

            mock_cls.assert_called_once()
            assert mock_cls.call_args.kwargs.get("device") == "cpu"

    def test_reranker_auto_device_resolves_correctly(self) -> None:
        with (
            patch("torch.cuda.is_available", return_value=False),
            patch("torch.backends.mps.is_available", return_value=False),
        ):
            assert Reranker._resolve_device("auto") == "cpu"

        with (
            patch("torch.cuda.is_available", return_value=False),
            patch("torch.backends.mps.is_available", return_value=True),
        ):
            assert Reranker._resolve_device("auto") == "mps"

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.backends.mps.is_available", return_value=False),
        ):
            assert Reranker._resolve_device("auto") == "cuda"

    def test_env_var_ate_kb_reranker_device_overrides_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setenv("ATE_KB_RERANKER_DEVICE", "cuda")
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            cfg = Config(
                {
                    "embedding": {"cache_dir": str(tmp_path), "local_files_only": False},
                    "retrieval": {"reranker": {"device": "${ATE_KB_RERANKER_DEVICE:-cpu}"}},
                }
            )
            reranker = Reranker(cfg)
            _ = reranker.model

            assert reranker.device == "cuda"
            assert mock_cls.call_args.kwargs.get("device") == "cuda"

    def test_rerank_broad_concept_uses_source_diverse_selection(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            model = MagicMock()
            # Scores: a1=0.99, a2=0.98, a3=0.97, b1=0.80, c1=0.70, d1=0.60
            model.predict.return_value = [0.99, 0.98, 0.97, 0.80, 0.70, 0.60]
            mock_cls.return_value = model

            cfg = Config(
                {
                    "retrieval": {
                        "reranker": {
                            "top_k": 5,
                            "broad_candidate_top_k": 16,
                            "broad_final_top_k": 4,
                            "broad_max_sources": 3,
                        }
                    }
                }
            )
            reranker = Reranker(cfg)
            chunks = [
                Chunk(id="a1", content="a1", chunk_type=ChunkType.PARAGRAPH, source_md="a.md"),
                Chunk(id="a2", content="a2", chunk_type=ChunkType.PARAGRAPH, source_md="a.md"),
                Chunk(id="a3", content="a3", chunk_type=ChunkType.PARAGRAPH, source_md="a.md"),
                Chunk(id="b1", content="b1", chunk_type=ChunkType.PARAGRAPH, source_md="b.md"),
                Chunk(id="c1", content="c1", chunk_type=ChunkType.PARAGRAPH, source_md="c.md"),
                Chunk(id="d1", content="d1", chunk_type=ChunkType.PARAGRAPH, source_md="d.md"),
            ]

            result = reranker.rerank("query", chunks, is_broad_concept=True)

            assert len(result) == 4
            ids = [c.id for c in result]
            # First pass: one per source, up to max_sources=3
            assert "a1" in ids
            assert "b1" in ids
            assert "c1" in ids
            # Second pass: fill remaining slot with highest-ranked remaining chunk
            assert "a2" in ids
            # d1 should be excluded because we already have 4 chunks
            assert "d1" not in ids

    def test_rerank_narrow_query_ignores_broad_settings(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            model = MagicMock()
            model.predict.return_value = [0.99, 0.98, 0.97, 0.80, 0.70, 0.60]
            mock_cls.return_value = model

            cfg = Config(
                {
                    "retrieval": {
                        "reranker": {
                            "top_k": 5,
                            "broad_candidate_top_k": 16,
                            "broad_final_top_k": 4,
                            "broad_max_sources": 3,
                        }
                    }
                }
            )
            reranker = Reranker(cfg)
            chunks = [
                Chunk(id="a1", content="a1", chunk_type=ChunkType.PARAGRAPH, source_md="a.md"),
                Chunk(id="a2", content="a2", chunk_type=ChunkType.PARAGRAPH, source_md="a.md"),
                Chunk(id="a3", content="a3", chunk_type=ChunkType.PARAGRAPH, source_md="a.md"),
                Chunk(id="b1", content="b1", chunk_type=ChunkType.PARAGRAPH, source_md="b.md"),
                Chunk(id="c1", content="c1", chunk_type=ChunkType.PARAGRAPH, source_md="c.md"),
                Chunk(id="d1", content="d1", chunk_type=ChunkType.PARAGRAPH, source_md="d.md"),
            ]

            result = reranker.rerank("query", chunks, is_broad_concept=False)

            # Narrow query should use default top_k=5, no source-diverse selection
            assert len(result) == 5
            ids = [c.id for c in result]
            assert ids == ["a1", "a2", "a3", "b1", "c1"]

    def test_rerank_broad_concept_preserves_order_within_source(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            model = MagicMock()
            model.predict.return_value = [0.90, 0.85, 0.80, 0.75]
            mock_cls.return_value = model

            cfg = Config(
                {
                    "retrieval": {
                        "reranker": {
                            "top_k": 5,
                            "broad_candidate_top_k": 16,
                            "broad_final_top_k": 4,
                            "broad_max_sources": 2,
                        }
                    }
                }
            )
            reranker = Reranker(cfg)
            chunks = [
                Chunk(id="a1", content="a1", chunk_type=ChunkType.PARAGRAPH, source_md="a.md"),
                Chunk(id="b1", content="b1", chunk_type=ChunkType.PARAGRAPH, source_md="b.md"),
                Chunk(id="a2", content="a2", chunk_type=ChunkType.PARAGRAPH, source_md="a.md"),
                Chunk(id="b2", content="b2", chunk_type=ChunkType.PARAGRAPH, source_md="b.md"),
            ]

            result = reranker.rerank("query", chunks, is_broad_concept=True)

            assert len(result) == 4
            ids = [c.id for c in result]
            # a1 and b1 from first pass, then a2 and b2 from second pass
            assert ids == ["a1", "b1", "a2", "b2"]

    def test_rerank_broad_concept_with_empty_source_md(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            model = MagicMock()
            model.predict.return_value = [0.99, 0.98, 0.80]
            mock_cls.return_value = model

            cfg = Config(
                {
                    "retrieval": {
                        "reranker": {
                            "top_k": 5,
                            "broad_candidate_top_k": 16,
                            "broad_final_top_k": 4,
                            "broad_max_sources": 3,
                        }
                    }
                }
            )
            reranker = Reranker(cfg)
            chunks = [
                Chunk(id="a1", content="a1", chunk_type=ChunkType.PARAGRAPH, source_md="a.md"),
                Chunk(id="no_src", content="no_src", chunk_type=ChunkType.PARAGRAPH, source_md=""),
                Chunk(id="b1", content="b1", chunk_type=ChunkType.PARAGRAPH, source_md="b.md"),
            ]

            result = reranker.rerank("query", chunks, is_broad_concept=True)

            ids = [c.id for c in result]
            # Empty source_md should be treated as a distinct source
            assert "a1" in ids
            assert "no_src" in ids
            assert "b1" in ids

    def test_rerank_broad_concept_demotes_low_utility_chunks(self) -> None:
        with patch("ate_rag_kb.retrieval.reranker.CrossEncoder") as mock_cls:
            model = MagicMock()
            model.predict.return_value = [0.99, 0.98, 0.80, 0.70]
            mock_cls.return_value = model

            reranker = Reranker(
                Config(
                    {
                        "retrieval": {
                            "reranker": {
                                "broad_candidate_top_k": 4,
                                "broad_final_top_k": 2,
                                "broad_max_sources": 2,
                            }
                        }
                    }
                )
            )
            chunks = [
                Chunk(
                    id="image",
                    content="Image: Site Control window (site-control.png)",
                    chunk_type=ChunkType.IMAGE,
                    source_md="image.md",
                ),
                Chunk(
                    id="title",
                    content="Site Control Window",
                    chunk_type=ChunkType.SECTION,
                    source_md="title.md",
                    section_title="Site Control Window",
                ),
                Chunk(
                    id="states",
                    content="Enable connects a site. Active executes the flow. Focus selects results.",
                    chunk_type=ChunkType.SECTION,
                    source_md="states.md",
                    section_title="The states of the sites",
                ),
                Chunk(
                    id="expanded",
                    content="Parallel, Serial and Semi-Parallel modes use Size and Cycle.",
                    chunk_type=ChunkType.SECTION,
                    source_md="expanded.md",
                    section_title="Expanded Site Control window",
                ),
            ]

            result = reranker.rerank("site control作用", chunks, is_broad_concept=True)

            assert [chunk.id for chunk in result] == ["states", "expanded"]
            assert reranker._last_rerank_stats["low_utility_rerank_candidate_count"] == 2

    def test_embedding_query_device_defaults_to_cpu_and_ingest_device_independent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ATE_KB_QUERY_DEVICE", "cpu")
        monkeypatch.setenv("ATE_KB_INGEST_DEVICE", "mps")
        cfg = Config(
            {
                "embedding": {
                    "device": "${ATE_KB_QUERY_DEVICE:-cpu}",
                    "ingest_device": "${ATE_KB_INGEST_DEVICE:-auto}",
                }
            }
        )
        assert cfg.get("embedding.device") == "cpu"
        assert cfg.get("embedding.ingest_device") == "mps"
