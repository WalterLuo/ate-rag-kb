# ATE RAG Knowledge Base

Agentic RAG system for ATE (Automatic Test Equipment) test engineers. Provides semantic search, advanced retrieval with parent-child expansion, and Claude Code integration over TDC/SmarTest technical documentation.

## Overview

This project ingests ATE technical documentation (Markdown + JSON metadata), chunks it with rich metadata, embeds it with `BAAI/bge-m3`, and stores vectors in Qdrant. A FastAPI layer exposes search, retrieval, Q&A, and document endpoints. Prompt templates and a Claude Code skill schema enable agentic consumption.

## Architecture

```
+----------------------------+
|  Markdown + JSON Metadata  |
+------------+---------------+
             |
             v
+----------------------------+
|   IngestionPipeline        |
|   (chunk, embed, index)    |
+------------+---------------+
             |
             v
+----------------------------+
|   Qdrant Vector Store      |
|   (hybrid: vector + BM25)  |
+------------+---------------+
             |
             v
+----------------------------+
|   FastAPI Server           |
|   /search /retrieve /ask   |
+------------+---------------+
             |
             v
+----------------------------+
|   Claude Code / Agents     |
|   (tools + prompt schema)  |
+----------------------------+
```

## Installation

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Optional OCR support:

```bash
uv sync --extra ocr
```

## Configuration

Copy and edit `configs/config.yaml`:

```yaml
data:
  raw_dir: "./data/raw"
  markdown_dir: "./data/raw/markdown"

embedding:
  model_name: "BAAI/bge-m3"
  device: "auto"

vector_store:
  type: "qdrant"
  host: "localhost"
  port: 6333
  collection_name: "ate_kb"
  use_local: true
  local_path: "./data/qdrant_storage"

api:
  host: "0.0.0.0"
  port: 8080
```

## Ingestion Workflow

Place Markdown files and their JSON metadata under `data/raw/markdown/` and `data/raw/json/`. Then run ingestion:

```bash
# Convenience script
python scripts/ingest.py

# Or via CLI
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental
```

Ingestion will:
1. Parse Markdown into hierarchical sections
2. Chunk by document, section, subsection, code block, and table
3. Compute embeddings with `BAAI/bge-m3`
4. Upsert into Qdrant with full metadata payloads

## API Usage

Start the server:

```bash
python scripts/serve.py
# or
uv run -m ate_rag_kb.cli.main serve --host 0.0.0.0 --port 8080
```

### Health Check

```bash
curl http://localhost:8080/health
```

### Search

```bash
curl -X POST http://localhost:8080/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "timing set configuration", "top_k": 5, "filters": {"platform": "TDC"}}'
```

### Retrieve (with expansion + reranking)

```bash
curl -X POST http://localhost:8080/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "pattern burst programming",
    "top_k": 10,
    "expand_parents": true,
    "expand_siblings": true,
    "rerank": true,
    "compress": true
  }'
```

### Ask (agent-friendly)

```bash
curl -X POST http://localhost:8080/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How do I configure a timing set in SmarTest?",
    "top_k": 8
  }'
```

Response includes `chunks`, `citations`, `toc_paths`, and `source_files` for downstream agents.

### Related Chunks

```bash
curl -X POST http://localhost:8080/api/v1/related \
  -H "Content-Type: application/json" \
  -d '{"chunk_id": "chunk-uuid-123"}'
```

### Get Document

```bash
curl http://localhost:8080/api/v1/document/smarTest_timing_guide.md
```

## Claude Code Integration

The project exposes a Claude Code skill schema in `src/ate_rag_kb/prompts/claude_code.py`.

Available tools:
- `ask_tdc` — general TDC/SmarTest questions
- `find_flow` — test flow documentation
- `find_api` — API reference lookup
- `find_timing` — timing configuration docs
- `find_pattern` — pattern programming docs

To integrate, register the skill with Claude Code and point it at the running API server. Each tool accepts a `query` and optional `top_k`, and returns structured chunks with citations.

Example tool result builder:

```python
from ate_rag_kb.prompts import build_tool_result, CLAUDE_CODE_TOOLS

result = build_tool_result(
    tool_name="find_timing",
    query="timing set edge placement",
    chunks=[{"content": "...", "source_md": "timing.md", "score": 0.95}],
)
```

## Evaluation

Run automated retrieval evaluation against a JSONL dataset:

```bash
python scripts/run_eval.py
```

This loads questions from `eval/v1/questions.jsonl`, runs them through the retrieval pipeline, and writes JSON + Markdown reports to `./reports/`. Metrics computed: hit@k, recall@k, MRR@k, source_precision@k.

### Evaluation Dataset Format

Each line in `eval/v1/questions.jsonl` is a JSON object:

```json
{"id": "q1", "query": "How to configure drive edge in TDC?", "expected_chunk_ids": ["c1"], "expected_source_mds": ["timing.md"], "category": "Timing"}
```

## Project Structure

```
ate-rag-kb/
├── configs/
│   └── config.yaml
├── data/
│   ├── raw/
│   └── qdrant_storage/
├── eval/
│   └── v1/
│       ├── manifest.json
│       └── questions.jsonl
├── scripts/
│   ├── ingest.py
│   ├── serve.py
│   └── run_eval.py
├── src/
│   └── ate_rag_kb/
│       ├── api/
│       │   ├── __init__.py
│       │   ├── server.py
│       │   ├── routes.py
│       │   └── models.py
│       ├── chunking/
│       │   └── models.py
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── dataset_loader.py
│       │   ├── formatters.py
│       │   ├── metrics.py
│       │   ├── models.py
│       │   └── runner.py
│       ├── prompts/
│       │   ├── __init__.py
│       │   ├── templates.py
│       │   └── claude_code.py
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       └── utils/
│           ├── config.py
│           ├── logging.py
│           └── paths.py
├── tests/
└── README.md
```

## Future Extensibility

- **Multi-modal retrieval**: Extend chunking to include image OCR and table extraction.
- **Re-ranker upgrades**: Swap `bge-reranker-v2-m3` for a domain-fine-tuned cross-encoder.
- **Agentic loops**: Use `/ask` + `related` endpoints to build iterative research agents.
- **Streaming responses**: Add SSE to `/ask` for real-time citation streaming.
- **Auth & rate limiting**: Add API key middleware and per-user rate limits.
- **Alternative vector stores**: Abstract storage behind a repository interface to support Milvus, Weaviate, or pgvector.

## License

MIT
