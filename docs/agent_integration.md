# Agent Integration Guide

Integrate the ATE RAG Knowledge Base with your coding agent (Claude Code,
OpenClaw, Codex, Cursor) to query ATE platform documentation directly from your
development workflow.

## Overview

The ATE KB exposes 6 tools via MCP (Model Context Protocol). Your agent can
search, retrieve, ask, and browse technical documentation with full citation
support.

## Qdrant Server Setup (Required)

The default configuration uses **Qdrant server mode** (`url: http://localhost:6333`).
You must start Qdrant **before** ingesting documents or running MCP/API.

```bash
# Docker Compose (recommended)
docker compose up -d qdrant

# Or docker run
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/data/qdrant_server:/qdrant/storage \
  qdrant/qdrant:latest
```

After Qdrant is running, ingest documents:

```bash
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown
```

Then verify:

```bash
uv run -m ate_rag_kb.cli.main status
```

### Local Mode (Not Recommended for Multi-Process)

For single-process debugging only, set `use_local: true` in
`configs/config.yaml`:

```yaml
vector_store:
  use_local: true
  local_path: "./data/qdrant_storage"
```

> **Warning:** Local mode locks the storage directory. Running MCP + CLI + API
> concurrently will trigger `portalocker.AlreadyLocked`. Use server mode for
> any real workflow.

## Claude Code Configuration

### Option 1: MCP (Recommended)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or equivalent:

```json
{
  "mcpServers": {
    "ate-kb": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/ate-rag-kb",
        "-m",
        "ate_rag_kb.cli.main",
        "mcp"
      ],
      "env": {
        "CONFIG_PATH": "/path/to/ate-rag-kb/configs/config.yaml"
      }
    }
  }
}
```

Restart Claude Code. The agent will auto-discover `ate_kb.*` tools.

### Option 2: HTTP API

If MCP is unavailable, configure Claude Code to call the FastAPI endpoints
directly via custom tools. Start the API server:

```bash
uv run -m ate_rag_kb.cli.main serve --host 0.0.0.0 --port 8080
```

## OpenClaw Configuration

OpenClaw supports MCP servers. Add the following to your OpenClaw configuration:

```json
{
  "mcpServers": {
    "ate-kb": {
      "command": "uv",
      "args": [
        "run",
        "-m",
        "ate_rag_kb.cli.main",
        "mcp"
      ],
      "cwd": "/path/to/ate-rag-kb"
    }
  }
}
```

## Codex Configuration

Codex MCP support varies by version. If your Codex client supports MCP,
configure it similarly to Claude Code:

```json
{
  "mcpServers": {
    "ate-kb": {
      "command": "uv",
      "args": [
        "run",
        "-m",
        "ate_rag_kb.cli.main",
        "mcp"
      ],
      "env": {
        "CONFIG_PATH": "/path/to/ate-rag-kb/configs/config.yaml"
      }
    }
  }
}
```

## Beta Validation

Before onboarding engineers, complete the formal validation steps:

- [Agent E2E Validation](agent_e2e_validation.md) — confirm MCP discovery, tool
  calls, citations, and pagination
- [Beta Checklist](beta_checklist.md) — 10-question trial with pass/fail criteria

Quick-start MCP config:

```bash
cp .mcp.example.json .mcp.json
# Replace /path/to/ate-rag-kb with your absolute project path
```

## Agent Usage Rules

When using ATE KB tools, follow these rules:

### 0. Default Contract

Engineers should ask ATE domain questions directly. The agent must choose the
retrieval path and should not ask the engineer whether to use MCP, CLI, grep, or
raw markdown files.

For any question about ATE documentation, SmarTest, TDC, V93000, pin
configuration, timing, levels, patterns, DPS, PMU, test flow, tester behavior,
command syntax, or API references:

- Use MCP tools first.
- Prefer `ate_kb.retrieve` for specific technical answers.
- Prefer `ate_kb.ask` for direct Q&A that needs citations.
- Use `ate_kb.get_document` only after relevant `source_md` files are identified.
- Use `ate_kb.search` only for exploratory discovery or source-file location.
- Do not use `uv run -m ate_rag_kb.cli.main search`, shell grep, `rg`, or manual
  raw markdown reads as the first step.
- Fall back to CLI/file reads only when MCP tools are unavailable, fail, or
  return insufficient context.

### 1. Tool Selection

- Use `ate_kb.retrieve` as the default tool for specific ATE technical questions
- Use `ate_kb.ask` for direct Q&A ("how do I configure drive edge?")
- Use `ate_kb.search` for quick exploratory lookups ("find docs about timing sets")
- Use `ate_kb.related` when a chunk is relevant but incomplete.
  Control sibling volume with `max_siblings` (default 2, max 10) to keep
  responses focused.
- Use `ate_kb.get_document` to read full API references after source discovery.
  This tool supports `limit`, `offset`, and `max_tokens`. For large documents,
  prefer small `limit` values (e.g. 20) and page through chunks rather than
  fetching the entire document at once.
- Use `ate_kb.status` to verify KB health before querying

### 2. Citation Requirements

**Every claim derived from ATE KB must include a citation.**

Required citation format:
```
[Source: {source_md}, Section: {section_title}, Chunk: {chunk_id}]
```

Example:
> To configure drive edge in TDC, use the MSET command with the `drive_edge`
> action. [Source: 118727.md, Section: Syntax, Chunk: sha256-abc...]

### 3. Confidence Handling

- If top chunk score < 0.5: warn user that results may be unreliable
- If no chunks returned: state clearly that the KB has no relevant information
- If sources conflict: present all perspectives with their sources

### 4. Follow-up Strategy

After initial retrieval:
1. Check if top result is directly relevant (score > 0.6)
2. If not, try `ate_kb.retrieve` with different query phrasing
3. If still poor, use `ate_kb.related` on the best-matching chunk
4. If document-level context needed, use `ate_kb.get_document`

## Recommended System Prompt

Add this to your agent's system prompt when ATE KB is active:

```
You have access to the ATE RAG Knowledge Base, which contains technical
documentation for TDC/SmarTest ATE platforms.

When answering questions about:
- Timing configuration (timesets, edges, waveforms)
- Pattern programming (bursts, vectors, loops)
- DPS/power management
- PMU/measurement
- Test flows and test programs
- API references

ALWAYS use MCP first. Use ate_kb.retrieve or ate_kb.ask to get grounded
context before answering. Do not start with CLI search, grep, rg, or manual
markdown reads unless MCP tools are unavailable or insufficient. Then synthesize
your answer, citing the source_md and section_title for every claim.

If the retrieved context is insufficient or low-confidence (score < 0.5),
say so explicitly. Do not hallucinate technical details.
```

## Query Best Practices

### Good Queries

- "How to configure drive edge in TDC?" (specific, includes platform)
- "DPS alarm 2034 meaning" (includes error code)
- "Pattern burst syntax example" (includes topic + intent)

### Bad Queries

- "timing" (too vague)
- "help with test" (no specific topic)
- "why does it fail" (no context)

## Low Confidence Response Strategy

When retrieval scores are low:

1. **Acknowledge uncertainty**: "The knowledge base has limited relevant
   information for this query."
2. **Present best available**: "Here are the closest matches, but they may not
   fully answer your question."
3. **Suggest alternatives**: "You may want to search for [related term] or
   consult the [specific document]."
4. **Never fabricate**: If the KB doesn't have the answer, say so.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| MCP tools not showing | Check `claude_desktop_config.json` syntax; restart Claude Code |
| Empty results | Verify documents are ingested (`ate_kb.status`) |
| Slow responses | Check Qdrant is running; consider reducing `top_k` |
| Wrong platform results | Add `filters: {"platform": "TDC"}` to queries |
| `mcp` command not found | Run `uv sync` to install MCP dependencies |
