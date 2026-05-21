# ate-rag-kb — ATE RAG Knowledge Base

## Project Goal

Agentic RAG system for ATE (Automatic Test Equipment) test engineers. Ingests
Markdown + JSON metadata, chunks with rich hierarchy, embeds with BAAI/bge-m3,
stores in Qdrant, and exposes retrieval + Q&A via FastAPI. Designed for
integration with Claude Code and other agentic tools.

## Core Architecture

```
Markdown + JSON  →  IngestionPipeline  →  Chunks  →  EmbeddingEncoder
                                                          ↓
FastAPI  ←  RetrievalPipeline  ←  QdrantVectorStore  ←  Vectors
   │
   └── /search      (basic semantic search)
   └── /retrieve    (hybrid + rerank + parent-child + compression)
   └── /ask         (retrieval + LLM synthesis + citations)
   └── /related     (parent/sibling/children for a chunk)
   └── /document    (all chunks for a source file)
```

## Directory Layout

| Path | Purpose |
|------|---------|
| `configs/config.yaml` | Central configuration (paths, models, retrieval params) |
| `src/ate_rag_kb/chunking/` | HierarchicalChunker: markdown → document/section/subsection/paragraph/code/table/image chunks |
| `src/ate_rag_kb/embedding/` | EmbeddingEncoder: sentence-transformers wrapper (bge-m3) |
| `src/ate_rag_kb/ingestion/` | IngestionPipeline + IncrementalIngestion (mtime-based change detection) |
| `src/ate_rag_kb/retrieval/` | HybridRetriever (vector + BM25), Reranker (cross-encoder), ParentChildExpander, ContextCompressor |
| `src/ate_rag_kb/vector_store/` | QdrantVectorStore wrapper + schema/index setup |
| `src/ate_rag_kb/api/` | FastAPI app, routes, Pydantic models |
| `src/ate_rag_kb/prompts/` | Prompt templates + Claude Code skill schema |
| `src/ate_rag_kb/evaluation/` | EvalRunner, metrics, dataset loader, formatters |
| `eval/` | Evaluation datasets, metrics, and reports |

## Common Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -q

# Run tests with coverage
uv run pytest tests/ --cov=src/ate_rag_kb --cov-report=term

# Ingest documents (full)
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown

# Ingest documents (incremental)
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental

# Start API server
uv run -m ate_rag_kb.cli.main serve --host 0.0.0.0 --port 8080

# Search from CLI
uv run -m ate_rag_kb.cli.main search "timing set configuration" --top-k 5

# Run retrieval eval
uv run python scripts/run_eval.py

# Check collection stats
uv run -m ate_rag_kb.cli.main status
```

## Key Flows

### Ingestion Flow
1. `cli/main.py _cmd_ingest` → `IncrementalIngestion.run_incremental`
2. Scan for new/modified `.md` files (compares mtime against `data/processed/ingestion_state.json`)
3. For each file: `_chunk_document` → `HierarchicalChunker.chunk`
4. `_embed_and_upsert` → `EmbeddingEncoder.encode` → `QdrantVectorStore.upsert_chunks`
5. Batch size defaults to 1000 chunks; memory errors trigger recursive halving

### Retrieval Flow
1. `RetrievalPipeline.retrieve` (async)
2. `HybridRetriever.retrieve` (sync, wrapped in `asyncio.to_thread`)
   - Vector search via `QdrantVectorStore.search` (top 20)
   - BM25 on vector candidates via `rank_bm25`
   - Reciprocal Rank Fusion
3. Optional: `Reranker.rerank` (cross-encoder, top 5)
4. Optional: `ParentChildExpander.expand` (batched `get_by_ids`)
5. Optional: `ContextCompressor.compress` (dedup, merge adjacent, token cap)

### /ask Flow
1. `routes.ask` → `retriever.search` (NOT retrieve; no rerank/expand by default)
2. Convert chunks to `ChunkResult`
3. Build `Citation` list from chunks
4. **TODO**: Currently NO LLM synthesis. Answer generation should be added here.

## Configuration Notes

- `configs/config.yaml` is the single source of truth.
- `Config` class supports dot-notation: `config.get("embedding.model_name")`.
- Chunking limits are read from `chunking.strategies.*.max_length` and `overlap`.
- The `paragraph_threshold` defaults to `max(800, section_max_length // 5)`.

## Development Conventions

### Immutability (CRITICAL)
- NEVER mutate existing Chunk objects. ALWAYS return new copies.
- Use `dataclasses.replace` when deriving modified chunks.
- Do not add new violations, and fix existing ones when encountered.

### Error Handling
- Explicit error handling at every level; never swallow exceptions silently.
- Ingestion isolates failures per file and per batch.

### Naming
- `camelCase` for variables/functions.
- `PascalCase` for types/components.
- Booleans prefixed with `is`/`has`/`should`.

### File Size
- Keep files under 800 lines; split large modules.

## Testing Strategy

- Unit tests for pure logic (chunking, config, filters).
- Mock external deps (Qdrant, embedding model) for fast unit tests.
- Integration tests should spin up real Qdrant (use temporary directory).
- **Coverage gate: 80% minimum.**
- Run ruff before commit: `uv run ruff check src/ tests/`

## Common Pitfalls

1. **Qdrant API drift**: The project uses `query_points` (not old `search`). Mock tests
   must match the actual API call.
2. **Embedding memory**: Large batches can OOM on MPS/CUDA. `_embed_and_upsert` has
   recursive halving, but batch_size should still be conservative on GPU.
3. **Global config singleton**: `get_config()` caches the first loaded config. In tests,
   call `reload_config()` or patch `_config_instance` to None.
4. **Local files only**: `embedding.local_files_only: true` means models must be
   pre-downloaded to `./embeddings/cache`. First-time setup requires internet.
5. **Chunk ID determinism**: IDs are SHA256 hashes of source + title + suffix + content
   snippet. Changing chunking logic changes IDs, breaking incremental state.

## Agent Rules

When modifying code, prioritize:

1. **Fix immutability violations** — return new objects instead of mutating.
2. **Read config from `config.yaml`** — do not add new hardcoded constants in source.
   If a new tunable is needed, add it to `config.yaml` and read via `Config.get()`.
3. **Keep functions under 50 lines** — extract helpers.
4. **Add tests for new logic** — maintain 80%+ coverage.
5. **Update eval dataset if behavior changes** — if chunking/retrieval logic changes,
   re-run `scripts/run_eval.py` and update golden expectations if the change is
   intentional.
6. **Do not break the incremental ingestion contract** — chunk IDs must remain
   deterministic for the same input; state file format changes need migration.

## Protected Directories

- `data/raw/` — Original documents. NEVER modify in-place; treat as immutable source.
- `data/qdrant_storage/` — Local Qdrant data. Do not manually delete while server is running.
- `data/processed/ingestion_state.json` — Incremental ingestion state. Do not edit manually.
- `embeddings/cache/` — Downloaded transformer models. Large; do not commit.
- `eval/v1/` — Evaluation datasets. Version-controlled; do not overwrite without bumping version.

## Recommended Next Tasks

1. **Add LLM synthesis to `/ask`** — use `RETRIEVAL_PROMPT` template + Claude API.
2. **Add docker-compose.yml** — define `qdrant` and `api` services for one-command startup.
3. **Add GitHub Actions CI** — pytest → ruff → eval gate.
4. **Expand eval dataset** — add more questions with expected_chunk_ids for finer-grained evaluation.
