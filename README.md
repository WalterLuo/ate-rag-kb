# ATE RAG Knowledge Base

> **Your coding agent's long-term memory for ATE platform knowledge.**

Query TDC/SmarTest technical documentation, APIs, error codes, and debug flows
directly from Claude Code, OpenClaw, Codex, or Cursor. Get reliable, cited
answers about timing, patterns, DPS, PMU, and test flows — without leaving your
IDE.

---

## Who Is This For

- Test engineers using Claude Code / OpenClaw / Codex / Cursor
- Teams maintaining ATE test programs (TDC, SmarTest, V93000)
- Anyone who needs reliable, cited answers about timing, patterns, DPS, PMU,
  test flows, and platform APIs

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Ingest your documents
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental

# 3. Start the MCP server (for agent integration)
uv run -m ate_rag_kb.cli.main mcp

# 4. Or start the HTTP API (for direct access)
uv run -m ate_rag_kb.cli.main serve --host 0.0.0.0 --port 8080
```

## Preparing Your Documents

Place Markdown files + JSON metadata under:

```
data/raw/
├── markdown/     # .md technical docs
├── json/         # optional metadata sidecars
└── assets/       # images, diagrams
```

Then run ingestion:

```bash
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental
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

## Available Agent Tools

| Tool | Description | Use When |
|------|-------------|----------|
| `ate_kb.search` | Quick semantic search | Finding relevant docs |
| `ate_kb.retrieve` | Deep retrieval with rerank + expansion | Comprehensive answers |
| `ate_kb.ask` | Structured Q&A with citations | Direct questions |
| `ate_kb.related` | Parent/sibling/children of a chunk | Need broader context |
| `ate_kb.get_document` | Full document chunks | Reading complete reference |
| `ate_kb.status` | Collection stats | Checking KB health |

All tools return structured JSON with `source_md`, `doc_title`,
`section_title`, `chunk_id`, `start_line`, and `end_line` for every result.

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

# Search from CLI
uv run -m ate_rag_kb.cli.main search "timing set configuration" --top-k 5

# Check collection stats
uv run -m ate_rag_kb.cli.main status
```

## License

MIT
