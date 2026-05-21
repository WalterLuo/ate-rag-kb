"""Unit tests for incremental ingestion."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ate_rag_kb.ingestion.incremental import IncrementalIngestion


class TestIncrementalIngestion:
    @pytest.fixture
    def state_file(self, tmp_path: Path) -> Path:
        return tmp_path / "state.json"

    @pytest.fixture
    def markdown_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "markdown"
        d.mkdir()
        return d

    @pytest.fixture
    def pipeline(self) -> SimpleNamespace:
        store = SimpleNamespace(delete_by_source=lambda x: None, upsert_chunks=lambda x: None)
        p = SimpleNamespace(
            vector_store=store,
            _chunk_document=lambda md, json, plat, dtype: [SimpleNamespace(content="hello")],
            _embed_and_upsert=lambda chunks: None,
            _detect_platform=lambda x: "",
            _detect_doc_type=lambda x: "reference",
        )
        return p

    def test_scan_new_files(self, markdown_dir: Path, state_file: Path, pipeline: object) -> None:
        (markdown_dir / "a.md").write_text("hello")
        incr = IncrementalIngestion(pipeline, state_file=state_file)

        new, modified = incr.scan_for_changes(markdown_dir)

        assert len(new) == 1
        assert new[0].name == "a.md"
        assert modified == []

    def test_scan_modified_files(self, markdown_dir: Path, state_file: Path, pipeline: object) -> None:
        md = markdown_dir / "a.md"
        md.write_text("hello")
        state_file.write_text('{"a.md": 1.0}')

        incr = IncrementalIngestion(pipeline, state_file=state_file)
        new, modified = incr.scan_for_changes(markdown_dir)

        assert new == []
        assert len(modified) == 1

    def test_scan_no_changes(self, markdown_dir: Path, state_file: Path, pipeline: object) -> None:
        md = markdown_dir / "a.md"
        md.write_text("hello")
        mtime = md.stat().st_mtime
        state_file.write_text(json.dumps({"a.md": mtime}))

        incr = IncrementalIngestion(pipeline, state_file=state_file)
        new, modified = incr.scan_for_changes(markdown_dir)

        assert new == []
        assert modified == []

    def test_run_incremental_updates_state(self, markdown_dir: Path, state_file: Path, pipeline: object) -> None:
        (markdown_dir / "a.md").write_text("hello")
        incr = IncrementalIngestion(pipeline, state_file=state_file)

        stats = incr.run_incremental(markdown_dir)

        assert stats["new"] == 1
        assert state_file.exists()
