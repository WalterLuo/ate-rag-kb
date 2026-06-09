"""Plugin install and routing-policy regression tests."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = PROJECT_ROOT / "scripts" / "install_mcp.py"


def load_installer():
    spec = importlib.util.spec_from_file_location("install_mcp", INSTALLER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_policy_block_is_appended_when_missing() -> None:
    installer = load_installer()
    original = "# Existing Rules\n\nKeep answers concise.\n"

    updated = installer.upsert_managed_block(original, installer.build_agent_policy_block())

    assert "# Existing Rules" in updated
    assert installer.POLICY_BLOCK_START in updated
    assert installer.POLICY_BLOCK_END in updated
    assert "tool_search" in updated
    assert "ate_kb.ask" in updated


def test_policy_block_is_updated_without_duplicate_markers() -> None:
    installer = load_installer()
    old = (
        "# Existing Rules\n\n"
        f"{installer.POLICY_BLOCK_START}\n"
        "old policy\n"
        f"{installer.POLICY_BLOCK_END}\n"
        "\nMore rules.\n"
    )

    updated = installer.upsert_managed_block(old, installer.build_agent_policy_block())

    assert updated.count(installer.POLICY_BLOCK_START) == 1
    assert updated.count(installer.POLICY_BLOCK_END) == 1
    assert "old policy" not in updated
    assert "More rules." in updated


def test_dry_run_does_not_write_policy_file(tmp_path: Path) -> None:
    installer = load_installer()
    policy_path = tmp_path / "AGENTS.md"
    policy_path.write_text("# Existing\n", encoding="utf-8")

    changed = installer.install_policy_file(policy_path, installer.build_agent_policy_block(), dry_run=True)

    assert changed is True
    assert policy_path.read_text(encoding="utf-8") == "# Existing\n"


def test_mcp_config_uses_absolute_project_path_and_config_path(tmp_path: Path) -> None:
    installer = load_installer()
    project_root = tmp_path / "ate-rag-kb"
    project_root.mkdir()

    config = installer.build_mcp_server_config(project_root)

    assert config["command"] == "uv"
    assert config["args"] == [
        "run",
        "--project",
        str(project_root),
        "-m",
        "ate_rag_kb.cli.main",
        "mcp",
    ]
    assert config["env"]["CONFIG_PATH"] == str(project_root / "configs" / "config.yaml")


def test_mcp_config_pins_retrieval_to_cpu(tmp_path: Path) -> None:
    installer = load_installer()
    project_root = tmp_path / "ate-rag-kb"
    project_root.mkdir()

    config = installer.build_mcp_server_config(project_root)

    assert config["env"]["ATE_KB_QUERY_DEVICE"] == "cpu"
    assert config["env"]["ATE_KB_RERANKER_DEVICE"] == "cpu"


def test_validate_plugin_install_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "validate_plugin_install.py")],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
