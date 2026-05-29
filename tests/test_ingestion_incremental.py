"""Unit tests for incremental ingestion with profile-isolated state."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ate_rag_kb.ingestion.incremental import (
    IncrementalIngestion,
    _build_profile,
    _compute_profile_key,
    _get_state_file,
)
from ate_rag_kb.utils.config import Config


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
        store = SimpleNamespace(
            delete_by_source=lambda x: None,
            upsert_chunks=lambda x: None,
        )
        p = SimpleNamespace(
            config=Config({"vector_store": {"mode": "server"}}),
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
        state_file.write_text('{"files": {"a.md": 1.0}}')

        incr = IncrementalIngestion(pipeline, state_file=state_file)
        new, modified = incr.scan_for_changes(markdown_dir)

        assert new == []
        assert len(modified) == 1

    def test_scan_no_changes(self, markdown_dir: Path, state_file: Path, pipeline: object) -> None:
        md = markdown_dir / "a.md"
        md.write_text("hello")
        mtime = md.stat().st_mtime
        state_file.write_text(json.dumps({"files": {"a.md": mtime}}))

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

    def test_state_is_profile_specific(self, tmp_path: Path) -> None:
        server_config = Config({"vector_store": {"mode": "server", "url": "http://localhost:6333"}})
        local_config = Config({"vector_store": {"mode": "local", "local_path": str(tmp_path / "local")}})

        server_state = _get_state_file(server_config)
        local_state = _get_state_file(local_config)

        assert server_state != local_state

    def test_needs_full_rebuild_when_no_state(self, markdown_dir: Path, state_file: Path, pipeline: object) -> None:
        incr = IncrementalIngestion(pipeline, state_file=state_file)
        assert incr.needs_full_rebuild() is True

    def test_needs_full_rebuild_on_profile_mismatch(self, markdown_dir: Path, state_file: Path, pipeline: object) -> None:
        incr = IncrementalIngestion(pipeline, state_file=state_file)
        # Simulate a stored state with a different profile
        state = {
            "_profile": {"mode": "local", "collection_name": "old"},
            "files": {},
        }
        incr.state_file.write_text(json.dumps(state))

        assert incr.needs_full_rebuild() is True

    def test_no_full_rebuild_when_profile_matches(self, markdown_dir: Path, state_file: Path, pipeline: object) -> None:
        incr = IncrementalIngestion(pipeline, state_file=state_file)
        profile = _build_profile(pipeline.config)
        state = {"_profile": profile, "files": {}}
        incr.state_file.write_text(json.dumps(state))

        assert incr.needs_full_rebuild() is False

    def test_needs_full_rebuild_on_schema_version_change(self, markdown_dir: Path, state_file: Path, pipeline: object) -> None:
        incr = IncrementalIngestion(pipeline, state_file=state_file)
        current_profile = _build_profile(pipeline.config)
        # Simulate old state with schema_version 1
        old_profile = {**current_profile, "schema_version": 1}
        state = {"_profile": old_profile, "files": {}}
        incr.state_file.write_text(json.dumps(state))

        assert incr.needs_full_rebuild() is True

    def test_legacy_state_renamed(self, tmp_path: Path, pipeline: object) -> None:
        legacy = tmp_path / "ingestion_state.json"
        legacy.write_text('{"doc.md": 1.0}')
        # Monkey-patch LEGACY_STATE_FILE for this test
        from ate_rag_kb.ingestion import incremental as incr_mod
        original_legacy = incr_mod.LEGACY_STATE_FILE
        try:
            incr_mod.LEGACY_STATE_FILE = legacy
            IncrementalIngestion(pipeline, state_file=tmp_path / "new_state.json")
            assert not legacy.exists()
            assert (tmp_path / "ingestion_state.json.legacy").exists()
        finally:
            incr_mod.LEGACY_STATE_FILE = original_legacy


class TestProfileKey:
    def test_same_config_same_key(self) -> None:
        cfg = Config({"vector_store": {"mode": "server"}})
        assert _compute_profile_key(cfg) == _compute_profile_key(cfg)

    def test_different_mode_different_key(self) -> None:
        server = Config({"vector_store": {"mode": "server"}})
        local = Config({"vector_store": {"mode": "local"}})
        assert _compute_profile_key(server) != _compute_profile_key(local)

    def test_different_documents_different_key(self) -> None:
        cfg1 = Config({"documents": {"enabled_ecosystems": ["v93000"]}})
        cfg2 = Config({"documents": {"enabled_ecosystems": ["v93000", "igxl"]}})
        assert _compute_profile_key(cfg1) != _compute_profile_key(cfg2)

    def test_server_mode_without_url_uses_host_port(self) -> None:
        cfg = Config({"vector_store": {"mode": "server", "host": "qdrant", "port": 9999}})
        profile = _build_profile(cfg)
        assert profile["endpoint"] == "qdrant:9999"

    def test_server_mode_with_url_uses_url(self) -> None:
        cfg = Config({"vector_store": {"mode": "server", "url": "http://qdrant:6333"}})
        profile = _build_profile(cfg)
        assert profile["endpoint"] == "http://qdrant:6333"

    def test_local_mode_uses_local_path(self) -> None:
        cfg = Config({"vector_store": {"mode": "local", "local_path": "/tmp/qdrant"}})
        profile = _build_profile(cfg)
        assert profile["endpoint"] == "/tmp/qdrant"

    def test_legacy_use_local_normalizes_to_local(self) -> None:
        cfg = Config({"vector_store": {"use_local": True, "local_path": "/tmp/qdrant"}})
        profile = _build_profile(cfg)
        assert profile["mode"] == "local"
        assert profile["endpoint"] == "/tmp/qdrant"

    def test_legacy_no_mode_no_use_local_normalizes_to_server(self) -> None:
        cfg = Config({"vector_store": {"host": "qdrant", "port": 9999}})
        profile = _build_profile(cfg)
        assert profile["mode"] == "server"
        assert profile["endpoint"] == "qdrant:9999"

    def test_different_servers_have_different_keys(self) -> None:
        cfg1 = Config({"vector_store": {"mode": "server", "host": "qdrant1", "port": 6333}})
        cfg2 = Config({"vector_store": {"mode": "server", "host": "qdrant2", "port": 6333}})
        assert _compute_profile_key(cfg1) != _compute_profile_key(cfg2)
