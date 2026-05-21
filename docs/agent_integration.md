# Agent Integration Guide

Integrate the ATE RAG Knowledge Base with your coding agent (Claude Code,
OpenClaw, Codex, Cursor) to query ATE platform documentation directly from your
development workflow.

## Overview

The ATE KB exposes 6 tools via MCP (Model Context Protocol). Your agent can
search, retrieve, ask, and browse technical documentation with full citation
support.

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

## Agent Usage Rules

When using ATE KB tools, follow these rules:

### 1. Tool Selection

- Use `ate_kb.search` for quick lookups ("find docs about timing sets")
- Use `ate_kb.retrieve` for deep research ("explain edge placement with examples")
- Use `ate_kb.ask` for direct Q&A ("how do I configure drive edge?")
- Use `ate_kb.related` when a chunk is relevant but incomplete
- Use `ate_kb.get_document` to read full API references
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

ALWAYS use ate_kb.retrieve first to get grounded context. Then synthesize
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
