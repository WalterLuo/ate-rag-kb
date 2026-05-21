"""Unit tests for configuration utilities."""

from __future__ import annotations

import pytest

from ate_rag_kb.utils.config import Config, get_config, reload_config


class TestConfig:
    def test_get_with_dot_notation(self) -> None:
        data = {"embedding": {"model_name": "BAAI/bge-m3", "batch_size": 32}}
        config = Config(data)

        assert config.get("embedding.model_name") == "BAAI/bge-m3"
        assert config.get("embedding.batch_size") == 32

    def test_get_returns_default_when_key_missing(self) -> None:
        config = Config({})

        assert config.get("missing.key", "default") == "default"
        assert config.get("missing.key") is None

    def test_get_returns_default_for_partial_path(self) -> None:
        config = Config({"embedding": {"model_name": "bge-m3"}})

        assert config.get("embedding.missing_key", 42) == 42

    def test_getitem_raises_key_error_when_missing(self) -> None:
        config = Config({})

        with pytest.raises(KeyError):
            _ = config["nonexistent.key"]

    def test_section_returns_subconfig(self) -> None:
        data = {"retrieval": {"top_k": 10, "enabled": True}}
        config = Config(data)
        sub = config.section("retrieval")

        assert isinstance(sub, Config)
        assert sub.get("top_k") == 10
        assert sub.get("enabled") is True

    def test_to_dict_returns_copy(self) -> None:
        data = {"a": 1}
        config = Config(data)
        d = config.to_dict()

        d["a"] = 99
        assert config.get("a") == 1

    def test_get_top_level_key(self) -> None:
        config = Config({"level": "INFO"})

        assert config.get("level") == "INFO"


class TestGetConfig:
    def test_get_config_returns_same_instance_on_subsequent_calls(self) -> None:
        reload_config()
        c1 = get_config()
        c2 = get_config()

        assert c1 is c2

    def test_reload_config_returns_new_instance(self) -> None:
        reload_config()
        c1 = get_config()
        c2 = reload_config()

        assert c1 is not c2
