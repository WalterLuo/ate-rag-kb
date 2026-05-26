# ATE RAG Knowledge Base

> **Your coding agent's long-term memory for ATE platform knowledge.**

Query TDC/SmarTest technical documentation, APIs, error codes, and debug flows
directly from Claude Code, OpenClaw, Codex, or Cursor. Get reliable, cited
answers about timing, patterns, DPS, PMU, and test flows — without leaving your
IDE.

---

## Built-In Documents

This repo ships with **pre-parsed TDC/SmarTest technical documentation**.
You do not need to find, convert, or format any documents — they are already
placed under `./data/raw/markdown/`.

**Built-in coverage:**

| Platform | Version | Content |
|----------|---------|---------|
| ADVANTEST V93000 | SmarTest 7.4.3 / 7.10.11 | PinConfig, Level, Timing, Test Flow, SmartRDI, TML, DPS, PMU, Digital, TMU, RF |

**First-time setup (approx. 15-30 min):**

```bash
# 1. Install dependencies
uv sync

# 2. Start Qdrant server (see Qdrant Server Setup below)
docker compose up -d qdrant

# 3. Download the embedding model (bge-m3, ~2.2 GB)
#    Automatically cached to ./embeddings/cache/

# 4. Ingest the built-in documents into Qdrant
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown

# 5. Start the MCP server and connect your agent
uv run -m ate_rag_kb.cli.main mcp
```

> **Note:** The embedding model cache (`./embeddings/cache/`) is **not**
> committed to git due to its large size. The ingestion step is required once
> after cloning.
>
> **Server mode is the default.** By default the KB connects to
> `http://localhost:6333` (Qdrant server). Local file mode (`./data/qdrant_storage/`)
> is available for single-process development only and will trigger
> `portalocker.AlreadyLocked` if multiple processes access it simultaneously.

---

## Who Is This For

- Test engineers using Claude Code / OpenClaw / Codex / Cursor
- Teams maintaining ATE test programs (TDC, SmarTest, V93000)
- Anyone who needs reliable, cited answers about timing, patterns, DPS, PMU,
  test flows, and platform APIs

## Qdrant Server Setup

The default `configs/config.yaml` uses **server mode** (`url: http://localhost:6333`).
Start Qdrant before ingesting or querying:

```bash
# Via Docker Compose (recommended)
docker compose up -d qdrant

# Or via docker run
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/data/qdrant_server:/qdrant/storage \
  qdrant/qdrant:latest
```

Qdrant data is persisted to `./data/qdrant_server/` (separate from the legacy
local-mode `./data/qdrant_storage/` to avoid lock conflicts).

### Local Mode (Single-Process Dev Only)

If you need local mode for quick debugging, set `use_local: true` in
`configs/config.yaml`:

```yaml
vector_store:
  use_local: true
  local_path: "./data/qdrant_storage"
```

> Warning: Local mode locks the storage directory. Only one process can access
> it at a time. Do **not** use local mode when running MCP + CLI + API
> concurrently.

## Migration from Local Mode

If you previously ingested into `./data/qdrant_storage/` (local mode) and want
to switch to server mode:

1. Start the Qdrant server (`docker compose up -d qdrant`).
2. Re-run ingestion (server collections are independent of local files):
   ```bash
   uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown
   ```
3. Verify:
   ```bash
   uv run -m ate_rag_kb.cli.main status
   ```

There is no automatic migration path from local files to server collections;
re-ingestion is required once.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Start Qdrant server
docker compose up -d qdrant

# 3. Ingest documents (built-in docs are already in ./data/raw/markdown)
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental

# 4. Verify the collection
uv run -m ate_rag_kb.cli.main status

# 5. Start the MCP server (for agent integration)
uv run -m ate_rag_kb.cli.main mcp

# 6. Or start the HTTP API (for direct access)
uv run -m ate_rag_kb.cli.main serve --host 0.0.0.0 --port 8080
```

## Adding Your Own Documents

If you have additional Markdown files + JSON metadata, place them under:

```
data/raw/
├── markdown/     # .md technical docs (built-in docs already here)
├── json/         # optional metadata sidecars
└── assets/       # images, diagrams
```

Then run ingestion:

```bash
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental
```

## Beta Validation

Before using the KB with real engineers, run:

1. [Agent E2E Validation](docs/agent_e2e_validation.md) — step-by-step verification
2. [Beta Checklist](docs/beta_checklist.md) — 10-question trial with pass criteria

Copy the example MCP config before starting:

```bash
cp .mcp.example.json .mcp.json
# Edit .mcp.json and replace /path/to/ate-rag-kb with your absolute path
```

## Agent Integration

### Claude Code (MCP — Recommended)

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

For detailed configuration and usage rules, see
[docs/agent_integration.md](docs/agent_integration.md).

### Default Agent Behavior

When an engineer asks an ATE technical question, the agent should use MCP tools
first and choose the retrieval strategy itself. The normal path is
`ate_kb.retrieve` or `ate_kb.ask`, followed by `ate_kb.get_document` only when a
full source document is needed. CLI search, grep, and manual markdown reads are
fallbacks for unavailable or insufficient MCP results, not the default workflow.

## Available Agent Tools

| Tool | Description | Use When |
|------|-------------|----------|
| `ate_kb.search` | Quick semantic search | Finding relevant docs |
| `ate_kb.retrieve` | Deep retrieval with rerank + expansion | Comprehensive answers |
| `ate_kb.ask` | Structured Q&A with citations | Direct questions |
| `ate_kb.related` | Parent/sibling/children of a chunk | Need broader context |
| `ate_kb.get_document` | Paginated document chunks (`limit`/`offset`) | Reading full reference after discovery |
| `ate_kb.status` | Collection stats | Checking KB health |

All tools return structured JSON with `source_md`, `doc_title`,
`section_title`, `chunk_id`, `start_line`, and `end_line` for every result.

`ate_kb.get_document` supports pagination (`limit`, `offset`) and a
`max_tokens` budget. Agents should prefer small `limit` values (e.g. 20) and
page through large documents rather than fetching all chunks at once.

## Evaluation

Run retrieval evaluation:

```bash
uv run python scripts/run_eval.py
```

Metrics: `hit@k`, `recall@k`, `MRR@k`, `source_precision@k`.

Current baseline (50 questions):

| Metric | Value |
|--------|-------|
| `source_precision@5` | 1.0000 |
| `failed_count` | 0 |

## Project Architecture

```
Markdown + JSON  ->  IngestionPipeline  ->  Chunks  ->  EmbeddingEncoder
                                                            |
                                                            v
FastAPI / MCP  <-  RetrievalPipeline  <-  QdrantVectorStore  <-  Vectors

RetrievalPipeline:
  HybridRetriever (vector + BM25)
  -> Reranker (cross-encoder)
  -> ParentChildExpander
  -> ContextCompressor
```

## Development Commands

```bash
# Run tests
uv run pytest tests/ -q

# Run tests with coverage
uv run pytest tests/ --cov=src/ate_rag_kb --cov-report=term

# Lint
uv run ruff check src/ tests/

# Search from CLI (developer/debugging fallback)
uv run -m ate_rag_kb.cli.main search "timing set configuration" --top-k 5

# Check collection stats
uv run -m ate_rag_kb.cli.main status
```

## License

MIT
