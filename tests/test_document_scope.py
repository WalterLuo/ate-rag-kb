"""Unit tests for DocumentScope helper."""

from __future__ import annotations

from pathlib import Path

from ate_rag_kb.utils.config import Config
from ate_rag_kb.utils.scope import DocumentScope


class TestEcosystem:
    def test_no_filtering_allows_all(self) -> None:
        scope = DocumentScope(Config({}))
        assert scope.isEcosystemEnabled("v93000") is True
        assert scope.isEcosystemEnabled("igxl") is True

    def test_enabled_ecosystem_allowed(self) -> None:
        scope = DocumentScope(Config({"documents": {"enabled_ecosystems": ["v93000"]}}))
        assert scope.isEcosystemEnabled("v93000") is True
        assert scope.isEcosystemEnabled("igxl") is False

    def test_enabled_ecosystems_list(self) -> None:
        scope = DocumentScope(Config({"documents": {"enabled_ecosystems": ["v93000", "igxl"]}}))
        assert scope.enabledEcosystems() == ["v93000", "igxl"]

    def test_igxl_enabled_overrides_enabled_ecosystems_list(self) -> None:
        scope = DocumentScope(
            Config(
                {
                    "documents": {
                        "enabled_ecosystems": ["v93000"],
                        "igxl": {"enabled": True},
                    }
                }
            )
        )
        assert scope.isEcosystemEnabled("igxl") is True

    def test_igxl_disabled_is_authoritative(self) -> None:
        scope = DocumentScope(
            Config(
                {
                    "documents": {
                        "enabled_ecosystems": ["v93000", "igxl"],
                        "igxl": {"enabled": False},
                    }
                }
            )
        )
        assert scope.isEcosystemEnabled("igxl") is False


class TestIgxl:
    def test_disabled_by_default(self) -> None:
        scope = DocumentScope(Config({}))
        assert scope.isIgxlEnabled() is False

    def test_enabled_when_configured(self) -> None:
        scope = DocumentScope(Config({"documents": {"igxl": {"enabled": True}}}))
        assert scope.isIgxlEnabled() is True


class TestSoftwareVersion:
    def test_no_filtering_allows_all(self) -> None:
        scope = DocumentScope(Config({}))
        assert scope.isSoftwareVersionEnabled("v93000", "smt7") is True
        assert scope.isSoftwareVersionEnabled("v93000", "smt8") is True

    def test_specific_version_enabled(self) -> None:
        scope = DocumentScope(
            Config({"documents": {"v93000": {"enabled_software_versions": ["smt7"]}}})
        )
        assert scope.isSoftwareVersionEnabled("v93000", "smt7") is True
        assert scope.isSoftwareVersionEnabled("v93000", "smt8") is False

    def test_general_docs_included_by_default(self) -> None:
        scope = DocumentScope(Config({}))
        assert scope.includeGeneralDocs("v93000") is True

    def test_general_docs_disabled(self) -> None:
        scope = DocumentScope(
            Config({"documents": {"v93000": {"include_general_docs": False}}})
        )
        assert scope.includeGeneralDocs("v93000") is False


class TestAmbiguity:
    def test_default_policy_empty(self) -> None:
        scope = DocumentScope(Config({}))
        assert scope.ambiguityPolicy() == ""
        assert scope.shouldAskWhenMultiple() is False

    def test_ask_when_multiple(self) -> None:
        scope = DocumentScope(
            Config({"documents": {"v93000": {"ambiguity_policy": "ask_when_multiple"}}})
        )
        assert scope.shouldAskWhenMultiple() is True


class TestShouldIngest:
    def test_allows_when_no_filtering(self) -> None:
        scope = DocumentScope(Config({}))
        assert scope.shouldIngest(Path("test.md"), "v93000", "smt7") is True

    def test_skips_disabled_ecosystem(self) -> None:
        scope = DocumentScope(Config({"documents": {"enabled_ecosystems": ["v93000"]}}))
        assert scope.shouldIngest(Path("test.md"), "igxl", "") is False

    def test_allows_igxl_when_igxl_enabled(self) -> None:
        scope = DocumentScope(
            Config(
                {
                    "documents": {
                        "enabled_ecosystems": ["v93000"],
                        "igxl": {"enabled": True},
                    }
                }
            )
        )
        assert scope.shouldIngest(Path("igxl/test.md"), "igxl", "") is True

    def test_allows_matching_version(self) -> None:
        scope = DocumentScope(
            Config(
                {
                    "documents": {
                        "enabled_ecosystems": ["v93000"],
                        "v93000": {"enabled_software_versions": ["smt7"]},
                    }
                }
            )
        )
        assert scope.shouldIngest(Path("test.md"), "v93000", "smt7") is True

    def test_skips_disabled_version(self) -> None:
        scope = DocumentScope(
            Config(
                {
                    "documents": {
                        "enabled_ecosystems": ["v93000"],
                        "v93000": {"enabled_software_versions": ["smt7"]},
                    }
                }
            )
        )
        assert scope.shouldIngest(Path("test.md"), "v93000", "smt8") is False

    def test_allows_general_docs_by_default(self) -> None:
        scope = DocumentScope(
            Config(
                {
                    "documents": {
                        "enabled_ecosystems": ["v93000"],
                        "v93000": {"enabled_software_versions": ["smt7"]},
                    }
                }
            )
        )
        assert scope.shouldIngest(Path("test.md"), "v93000", "") is True

    def test_skips_general_docs_when_disabled(self) -> None:
        scope = DocumentScope(
            Config(
                {
                    "documents": {
                        "enabled_ecosystems": ["v93000"],
                        "v93000": {
                            "enabled_software_versions": ["smt7"],
                            "include_general_docs": False,
                        },
                    }
                }
            )
        )
        assert scope.shouldIngest(Path("test.md"), "v93000", "") is False
