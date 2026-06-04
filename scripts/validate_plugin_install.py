#!/usr/bin/env python3
"""Validate plugin, skill, and agent-routing installation assets."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_json(path: Path, errors: list[str]) -> None:
    try:
        json.loads(read(path))
    except FileNotFoundError:
        errors.append(f"Missing JSON file: {path.relative_to(PROJECT_ROOT)}")
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path.relative_to(PROJECT_ROOT)}: {exc}")


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    result: dict[str, str] = {}
    for raw_line in text[4:end].splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def main() -> int:
    errors: list[str] = []

    for relative in [
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        ".cursor-plugin/plugin.json",
        ".agents/plugins/marketplace.json",
    ]:
        validate_json(PROJECT_ROOT / relative, errors)

    skill_path = PROJECT_ROOT / "skills" / "ate-kb-router" / "SKILL.md"
    require(skill_path.exists(), "Missing skills/ate-kb-router/SKILL.md", errors)
    if skill_path.exists():
        metadata = frontmatter(read(skill_path))
        description = metadata.get("description", "")
        require(metadata.get("name") == "ate-kb-router", "Skill name must be ate-kb-router", errors)
        require(bool(description), "Skill description is missing", errors)
        lower_description = description.lower()
        for keyword in ["smt7", "v93000", "ig-xl", "j750", "ate", "mcp", "ate_kb"]:
            require(
                keyword in lower_description,
                f"Skill description must include {keyword}",
                errors,
            )

    agents = read(PROJECT_ROOT / "AGENTS.md")
    claude = read(PROJECT_ROOT / "CLAUDE.md")
    gemini = read(PROJECT_ROOT / "GEMINI.md")
    installer = read(PROJECT_ROOT / "scripts" / "install_mcp.py")
    mcp_example = read(PROJECT_ROOT / ".mcp.example.json")

    require("Deferred MCP Bootstrap" in agents, "AGENTS.md missing Deferred MCP Bootstrap", errors)
    require("tool_search" in agents, "AGENTS.md missing tool_search bootstrap", errors)
    require("deferred MCP tool" in claude, "CLAUDE.md missing Codex deferred MCP rule", errors)
    require("mcp__ate-kb__ate_kb_ask" in claude, "CLAUDE.md missing Claude Code ask tool", errors)
    require("MCP tools first" in gemini or "Use MCP tools first" in gemini, "GEMINI.md missing MCP-first rule", errors)
    require("ate_kb.ask" in gemini, "GEMINI.md missing ate_kb.ask rule", errors)
    require("--install-agent-policy" in installer, "install_mcp.py missing --install-agent-policy", errors)
    require("--skip-agent-policy" in installer, "install_mcp.py missing --skip-agent-policy", errors)
    require('"--project"' in mcp_example, ".mcp.example.json must use --project", errors)
    require("CONFIG_PATH" in mcp_example, ".mcp.example.json must include CONFIG_PATH", errors)

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1

    print("[OK] Plugin install assets are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
