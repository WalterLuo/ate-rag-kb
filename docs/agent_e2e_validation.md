# Agent E2E Validation Guide

This guide walks you through formally verifying that `ate-rag-kb` is ready for
agent use with Claude Code, Codex, OpenClaw, or Cursor.

---

## 1. Validation Goals

Confirm the following before inviting real engineers:

- MCP server starts without errors
- Agent discovers all `ate_kb.*` tools
- `ate_kb.status` returns a healthy collection with chunks
- `ate_kb.retrieve` returns relevant, cited results
- `ate_kb.ask` returns structured answers with citations
- `ate_kb.get_document` supports pagination (`limit`, `offset`)
- Agent answers include `source_md`, `section_title`, and `chunk_id`
- Agent does **not** hallucinate when confidence is low or no results are found

---

## 2. Prerequisites

- `uv` is installed
- `uv sync` has been run
- Qdrant server is running (default: `http://localhost:6333`)
- Document ingestion is complete
- `configs/config.yaml` exists

### Start Qdrant Server

```bash
# Docker Compose (recommended)
docker compose up -d qdrant
```

### Ingest Documents

```bash
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental
```

### Verify Status

```bash
uv run -m ate_rag_kb.cli.main status
```

Expected output includes `status: ok` and `total_chunks > 0`.

If `status` fails or `total_chunks` is `0`:

1. Confirm Qdrant is running: `curl http://localhost:6333`
2. Re-run ingestion
3. Check `configs/config.yaml` uses server mode (`use_local: false`)

---

## 3. MCP Configuration

Copy the example configuration:

```bash
cp .mcp.example.json .mcp.json
```

Edit `.mcp.json` and replace `/path/to/ate-rag-kb` with the absolute path to this
repository on your machine.

### Claude Code

Add the server to `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or the equivalent path on your OS:

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

Restart Claude Code after saving.

### Codex / OpenClaw (Generic MCP)

Most MCP-compatible clients accept the same JSON structure. Point the client at
`.mcp.json` (or paste the `ate-kb` block into the client's MCP settings) and
restart the agent.

---

## 4. Start the MCP Server

```bash
uv run -m ate_rag_kb.cli.main mcp
```

Important notes:

- **stdio transport** does **not** print ordinary HTTP-like responses to the
  terminal.
- Logs are written to **stderr**.
- **stdout must remain clean** for JSON-RPC messages only.

If you see log lines in the terminal, that is expected (they go to stderr).
If you see JSON-RPC garbled by unrelated stdout output, check that no
`print()` statements or log misconfiguration are present in the codebase.

---

## 5. In-Agent Validation Steps

### Step 1 — Confirm Tools Are Visible

Ask the agent:

```text
What ATE KB tools do you have available?
```

Expected tool list:

- `ate_kb.search`
- `ate_kb.retrieve`
- `ate_kb.ask`
- `ate_kb.related`
- `ate_kb.get_document`
- `ate_kb.status`

If any tool is missing, restart the agent and verify the MCP configuration path.

---

### Step 2 — Call `ate_kb.status`

Prompt:

```text
请调用 ate_kb.status 检查 ATE KB 是否可用，并总结 collection 状态。
```

Expected results:

- `status` = `ok`
- `total_chunks` > 0
- `collection_name` = `ate_kb`
- `embedding_model` is non-empty

---

### Step 3 — Call `ate_kb.retrieve`

Prompt:

```text
请使用 ATE KB 查询：How to configure drive edge in TDC? 请给出带 source_md、section_title、chunk_id 的引用。
```

Expected results:

- Agent calls `ate_kb.retrieve` (or `ate_kb.ask`)
- Response contains timing / drive edge related content
- Answer includes citations such as:
  ```
  [Source: 118727.md, Section: Syntax, Chunk: sha256-abc...]
  ```

---

### Step 4 — Call `ate_kb.ask`

Prompt:

```text
请用 ate_kb.ask 回答：What is the difference between drive edge and compare edge? 并引用来源。
```

Expected results:

- Agent uses `ate_kb.ask`
- Answer is based on the returned `context_package`
- No fabricated details outside the provided context
- Citations include `source_md`, `section_title`, and `chunk_id`

---

### Step 5 — Call `ate_kb.get_document` with Pagination

Prompt:

```text
请先用 ATE KB 找到与 drive edge 相关的 source_md，然后用 ate_kb.get_document 读取该文档前 5 个 chunks，不要一次读取全文。
```

Expected results:

- Agent first calls `ate_kb.retrieve` or `ate_kb.ask` to discover `source_md`
- Then calls `ate_kb.get_document` with a `limit` parameter (e.g. `limit=5`)
- Response contains `has_more` and `next_offset`
- Agent does **not** fetch the entire document in one call

---

### Step 6 — Low-Confidence / No-Result Test

Prompt:

```text
请查询一个知识库可能没有的问题：How to repair a coffee machine with TDC timing APIs?
```

Expected results:

- Agent does **not** invent an answer
- Agent states that the KB may not contain relevant information
- If nearest results are returned, they are presented as "possibly related" with
  low-confidence noted

---

## 6. Pass Criteria

Beta is considered **ready** when **all** of the following are true:

| # | Criterion |
|---|-----------|
| 1 | All 6 MCP tools are visible to the agent |
| 2 | `ate_kb.status` returns `ok` with `total_chunks > 0` |
| 3 | At least 4 out of 5 typical questions return relevant citations |
| 4 | Every answer cites `source_md`, `section_title`, and `chunk_id` |
| 5 | `get_document` is called with `limit` and returns `has_more` / `next_offset` |
| 6 | No hallucination on out-of-domain or low-confidence queries |
| 7 | No JSON-RPC parse errors in MCP stdout |

---

## 7. Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Tools do not appear | MCP config path is wrong | Verify `.mcp.json` / Claude Code config uses absolute paths |
| `CONFIG_PATH` error | Config file missing or path is relative | Use absolute path to `configs/config.yaml` |
| `status` fails | Qdrant server not running | Start Qdrant: `docker compose up -d qdrant` |
| `status` fails | No ingestion or collection empty | Re-run `uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental` |
| `status` fails | `portalocker.AlreadyLocked` | You are using local mode with multiple processes. Switch to server mode in `configs/config.yaml` (`use_local: false`) |
| Very slow responses | First-time model load or oversized `top_k` | Wait for embedding model cache to warm up; reduce `top_k` in `configs/config.yaml` |
| `get_document` returns too much data | `limit` is too high | Use `limit=5` or `limit=20` |
| Agent omits citations | System prompt is not explicit enough | Use the recommended system prompt from `docs/agent_integration.md` |
| JSON-RPC parse errors | Something wrote to stdout | Check that logs go to stderr and no `print()` statements exist in MCP code |
