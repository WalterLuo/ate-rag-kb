"""Configuration management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class Config:
    """Simple attribute-access config backed by a nested dict."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        """Dot-notation access, e.g. config.get('embedding.model_name')."""
        parts = key.split(".")
        val = self._data
        for part in parts:
            if isinstance(val, dict) and part in val:
                val = val[part]
            else:
                return default
        return val

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None and key not in str(self._data):
            raise KeyError(key)
        return val

    def section(self, name: str) -> "Config":
        """Return a subsection as a new Config."""
        return Config(self._data.get(name, {}))

    def to_dict(self) -> dict[str, Any]:
        return self._data.copy()


_config_instance: Config | None = None


def get_config(path: Path | str | None = None) -> Config:
    """Load or return cached config."""
    global _config_instance
    if _config_instance is not None:
        return _config_instance
    if path is None:
        path = Path(__file__).resolve().parents[3] / "configs" / "config.yaml"
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    _config_instance = Config(data)
    return _config_instance


def reload_config(path: Path | str | None = None) -> Config:
    """Force reload config from disk."""
    global _config_instance
    _config_instance = None
    return get_config(path)
