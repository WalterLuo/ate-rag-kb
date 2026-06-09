# ATE RAG KB — Multi-Harness Plugin Installation

This document describes how to install and configure **ate-rag-kb** as a plugin
or MCP extension in various AI CLI tools.

## Prerequisites (All Platforms)

Before installing into any harness, ensure the project itself is ready:

1. **Python 3.10+** with [`uv`](https://docs.astral.sh/uv/) installed
2. **Clone the repo** and install dependencies:
   ```bash
   git clone https://github.com/WalterLuo/ate-rag-kb.git
   cd ate-rag-kb
   uv sync
   ```
3. **Models** downloaded to `embeddings/cache/` (see `scripts/package_models.py`)
4. **Qdrant** running (local or remote) and documents ingested:
   ```bash
   uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown
   ```

## Quick Setup (Recommended)

The automatic installer configures the harnesses that read external MCP
config files — **Claude Code, Cursor, and Codex** — and installs the managed
ATE KB Routing policy:

```bash
uv run python scripts/install_mcp.py --install-agent-policy
```

> Gemini CLI and OpenCode are **not** handled by this script. They wire up MCP
> through their own native mechanisms instead: Gemini reads `mcpServers` from
> `gemini-extension.json` on `gemini extensions install`, and OpenCode installs
> via its plugin manager (see `.opencode/INSTALL.md`).

Dry-run first to see what will change:

```bash
uv run python scripts/install_mcp.py --dry-run
```

Configure only specific harnesses:

```bash
uv run python scripts/install_mcp.py --harness claude,cursor
```

Only project-level configs (no global dotfiles):

```bash
uv run python scripts/install_mcp.py --project-only
```

Configure MCP only, without global agent policy:

```bash
uv run python scripts/install_mcp.py --skip-agent-policy
```

This is not recommended for Codex projectless sessions because the repository
`AGENTS.md` may not be loaded.

---

## Per-Harness Installation

### Claude Code

**Marketplace install (recommended):**

```bash
/plugin marketplace add WalterLuo/ate-rag-kb-marketplace
/plugin install ate-rag-kb@ate-rag-kb-marketplace
```

**Or install from this repo directly:**

```bash
/plugin install ate-rag-kb@git+https://github.com/WalterLuo/ate-rag-kb.git
```

**MCP Configuration:**

Claude Code supports MCP servers via `settings.json`. The install script
configures it automatically, or add manually:

```json
// ~/.claude/settings.json (global) or .claude/settings.json (project)
{
  "mcpServers": {
    "ate_kb": {
      "command": "uv",
      "args": ["run", "-m", "ate_rag_kb.cli.main", "mcp"]
    }
  }
}
```

**Verify:**

```
What V93000 timing set commands are available?
```

Claude Code should invoke `ate_kb.search` or `ate_kb.retrieve` automatically.

---

### Cursor

**Install from marketplace:**

```bash
/add-plugin ate-rag-kb
```

**Or search:**

Open Cursor Agent chat, search for "ate-rag-kb" in the plugin marketplace.

**MCP Configuration:**

Cursor uses `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "ate_kb": {
      "command": "uv",
      "args": ["run", "-m", "ate_rag_kb.cli.main", "mcp"]
    }
  }
}
```

The `scripts/install_mcp.py` configures this automatically.

---

### Codex CLI / Codex App

**Install from marketplace:**

```bash
/plugins
# Search for "ate-rag-kb" and select Install Plugin.
```

For local or team marketplace testing, add this repository's Codex marketplace
manifest first, then search for `ate-rag-kb`:

```bash
codex plugin marketplace add /path/to/ate-rag-kb/.agents/plugins/marketplace.json
```

Public Codex marketplace search requires publishing or registering that
marketplace entry outside this repository.

**MCP Configuration:**

Codex also supports MCP servers. Add to `~/.codex/settings.json`:

```json
{
  "mcpServers": {
    "ate_kb": {
      "command": "uv",
      "args": ["run", "-m", "ate_rag_kb.cli.main", "mcp"]
    }
  }
}
```

Or run `scripts/install_mcp.py --harness codex --install-agent-policy`.

After installation, restart Codex and run:

```bash
uv run python scripts/validate_plugin_install.py
uv run python scripts/validate_agent_routing_policy.py
```

---

### Gemini CLI

**Install the extension:**

```bash
gemini extensions install https://github.com/WalterLuo/ate-rag-kb.git
```

**Update later:**

```bash
gemini extensions update ate-rag-kb
```

Gemini CLI reads `gemini-extension.json` at the repo root. The manifest
declares the `ate-kb` MCP server (launched with `uv run ... mcp`) under
`mcpServers` and points to `GEMINI.md` as the context file. Paths use the
`${extensionPath}` variable so the extension stays portable across machines.
Installing the extension wires up the MCP server automatically; no manual
`mcpServers` editing is required.

---

### OpenCode

**Install via git-backed plugin:**

Add to your `opencode.json` (global or project-level):

```json
{
  "plugin": ["ate-rag-kb@git+https://github.com/WalterLuo/ate-rag-kb.git"]
}
```

Restart OpenCode. See `.opencode/INSTALL.md` for detailed instructions.

---

### GitHub Copilot CLI

**Register the marketplace:**

```bash
copilot plugin marketplace add WalterLuo/ate-rag-kb-marketplace
```

**Install the plugin:**

```bash
copilot plugin install ate-rag-kb@ate-rag-kb-marketplace
```

Copilot Chat in VS Code can also use MCP servers via
`~/.vscode/mcp.json` or workspace settings.

---

### Factory Droid

**Register the marketplace:**

```bash
droid plugin marketplace add https://github.com/WalterLuo/ate-rag-kb
droid plugin install ate-rag-kb@ate-rag-kb
```

---

## Plugin Files Reference

| Harness | Files in this repo |
|---------|-------------------|
| Claude Code | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` |
| Cursor | `.cursor-plugin/plugin.json` |
| Codex | `.codex-plugin/plugin.json` |
| Gemini CLI | `gemini-extension.json`, `GEMINI.md` |
| OpenCode | `.opencode/INSTALL.md` |
| Claude / Cursor / Codex MCP installer | `scripts/install_mcp.py` |

## Troubleshooting

### MCP server not starting

1. Verify `uv run -m ate_rag_kb.cli.main mcp` works from the project root.
2. Check that models exist in `embeddings/cache/`.
3. Ensure Qdrant is reachable (check `configs/config.yaml`).

### Plugin not loading

1. Confirm the plugin manifest syntax is valid JSON.
2. Check the AI tool's logs for plugin loading errors.
3. For marketplace installs, verify the marketplace URL is reachable.

### Model cache errors

If you see "Local model cache not found", the embedding models are missing.
Unpack the model archive or download them:

```bash
# After unpacking ate-rag-kb-models.zip into project root
uv run python scripts/verify_models.py
```

## Architecture Notes

- **MCP-first:** All harnesses that support MCP (Claude Code, Cursor, Codex,
  Copilot Chat) connect to the same `ate_rag_kb.cli.main mcp` stdio server.
- **Routing skill:** `skills/ate-kb-router/SKILL.md` tells skill-aware agents to
  expose and call `ate_kb` before web or shell fallbacks.
- **Managed policy:** `scripts/install_mcp.py --install-agent-policy` appends or
  updates a managed ATE KB Routing block in global agent instructions without
  overwriting user rules.
- **Context files:** `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` provide
  harness-specific instructions so each AI tool knows how to use `ate_kb` tools.
- **Plugin manifests:** Each harness has its own manifest format in a dedicated
  directory (`.claude-plugin/`, `.cursor-plugin/`, `.codex-plugin/`).
