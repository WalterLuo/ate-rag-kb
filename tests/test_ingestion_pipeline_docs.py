"""Unit tests for ingestion pipeline document ingestion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from ate_rag_kb.ingestion.pipeline import IngestionPipeline
from ate_rag_kb.utils.config import Config


class TestIngestDocument:
    @pytest.fixture
    def pipeline(self, tmp_path: Path) -> IngestionPipeline:
        cfg = Config({"data": {"markdown_dir": str(tmp_path), "json_dir": str(tmp_path)}})
        encoder = MagicMock()
        encoder.encode.return_value = np.array([[0.1, 0.2]])
        vs = MagicMock()
        return IngestionPipeline(cfg, encoder, vs)

    def test_ingest_document_no_json(self, pipeline: IngestionPipeline, tmp_path: Path) -> None:
        md = tmp_path / "test.md"
        md.write_text("# Hello\n\nworld")
        chunks = pipeline.ingest_document(md)
        assert len(chunks) > 0
        pipeline.vector_store.upsert_chunks.assert_called_once()

    def test_ingest_document_with_json(self, pipeline: IngestionPipeline, tmp_path: Path) -> None:
        md = tmp_path / "test.md"
        md.write_text("# Hello")
        json_path = tmp_path / "test.json"
        json_path.write_text('{"title": "Test"}')
        chunks = pipeline.ingest_document(md, json_path)
        assert chunks[0].doc_title == "Test"

    def test_ingest_document_sets_platform_and_doc_type(self, pipeline: IngestionPipeline, tmp_path: Path) -> None:
        md = tmp_path / "test.md"
        md.write_text("content")
        chunks = pipeline.ingest_document(md, platform="TDC", doc_type="guide")
        assert chunks[0].platform == "TDC"
        assert chunks[0].doc_type == "guide"


class TestIngestDirectory:
    def test_ingest_directory_counts_chunks(self, tmp_path: Path) -> None:
        cfg = Config({"data": {"markdown_dir": str(tmp_path), "json_dir": str(tmp_path)}})
        encoder = MagicMock()
        encoder.encode.return_value = np.array([[0.1, 0.2]])
        vs = MagicMock()
        pipeline = IngestionPipeline(cfg, encoder, vs)
        md = tmp_path / "doc.md"
        md.write_text("content")
        total = pipeline.ingest_directory(tmp_path)
        assert total > 0

    def test_ingest_directory_skips_failed_files(self, tmp_path: Path) -> None:
        cfg = Config({"data": {"markdown_dir": str(tmp_path), "json_dir": str(tmp_path)}})
        encoder = MagicMock()
        vs = MagicMock()
        pipeline = IngestionPipeline(cfg, encoder, vs)
        md = tmp_path / "bad.md"
        md.write_text("content")
        pipeline._chunk_document = MagicMock(side_effect=Exception("fail"))  # type: ignore[method-assign]
        total = pipeline.ingest_directory(tmp_path)
        assert total == 0

    def test_ingest_directory_with_json_dir(self, tmp_path: Path) -> None:
        cfg = Config({"data": {"markdown_dir": str(tmp_path), "json_dir": str(tmp_path / "json")}})
        encoder = MagicMock()
        encoder.encode.return_value = np.array([[0.1, 0.2]])
        vs = MagicMock()
        pipeline = IngestionPipeline(cfg, encoder, vs)
        md = tmp_path / "doc.md"
        md.write_text("content")
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        (json_dir / "doc.json").write_text('{"title": "Doc"}')
        total = pipeline.ingest_directory(tmp_path, json_dir)
        assert total > 0
