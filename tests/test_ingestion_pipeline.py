"""Unit tests for ingestion pipeline helpers."""

from __future__ import annotations

from pathlib import Path

from ate_rag_kb.ingestion.pipeline import IngestionPipeline


class TestDetectPlatform:
    def test_detects_j750(self) -> None:
        assert IngestionPipeline._detect_platform(Path("j750_guide.md")) == "J750"
        assert IngestionPipeline._detect_platform(Path("ultraflex_ref.md")) == "J750"

    def test_detects_smt7(self) -> None:
        assert IngestionPipeline._detect_platform(Path("smt7_api.md")) == "SMT7"
        assert IngestionPipeline._detect_platform(Path("smt8_flow.md")) == "SMT7"

    def test_detects_v93000(self) -> None:
        assert IngestionPipeline._detect_platform(Path("v93000_setup.md")) == "V93000"
        assert IngestionPipeline._detect_platform(Path("smartest_guide.md")) == "V93000"

    def test_detects_tdc(self) -> None:
        assert IngestionPipeline._detect_platform(Path("tdc_overview.md")) == "TDC"

    def test_unknown_returns_empty(self) -> None:
        assert IngestionPipeline._detect_platform(Path("unknown.md")) == ""


class TestDetectDocType:
    def test_detects_api(self) -> None:
        assert IngestionPipeline._detect_doc_type(Path("api_reference.md")) == "api"
        assert IngestionPipeline._detect_doc_type(Path("commands.md")) == "api"

    def test_detects_flow(self) -> None:
        assert IngestionPipeline._detect_doc_type(Path("testflow_guide.md")) == "flow"

    def test_detects_hardware_config(self) -> None:
        assert IngestionPipeline._detect_doc_type(Path("timing_setup.md")) == "hardware_config"
        assert IngestionPipeline._detect_doc_type(Path("pin_config.md")) == "hardware_config"

    def test_detects_guide(self) -> None:
        assert IngestionPipeline._detect_doc_type(Path("getting started.md")) == "guide"
        assert IngestionPipeline._detect_doc_type(Path("tutorial.md")) == "guide"

    def test_default_is_reference(self) -> None:
        assert IngestionPipeline._detect_doc_type(Path("random.md")) == "reference"
