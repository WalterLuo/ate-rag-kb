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

# 2. Download the embedding model (bge-m3, ~2.2 GB)
#    Automatically cached to ./embeddings/cache/

# 3. Ingest the built-in documents to build the vector database
#    Vectors are stored in ./data/qdrant_storage/
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown

# 4. Start the MCP server and connect your agent
uv run -m ate_rag_kb.cli.main mcp
```

> **Note:** The vector database (`./data/qdrant_storage/`) and embedding model
> cache (`./embeddings/cache/`) are **not** committed to git due to their large
> size. The ingestion step above is required once after cloning.

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

# 2. Ingest documents (built-in docs are already in ./data/raw/markdown)
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental

# 3. Start the MCP server (for agent integration)
uv run -m ate_rag_kb.cli.main mcp

# 4. Or start the HTTP API (for direct access)
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
