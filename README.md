# ATE RAG Knowledge Base

> **Your coding agent's long-term memory for ATE platform knowledge.**

Query ATE technical documentation, APIs, error codes, and debug flows directly
from Claude Code, Cursor, Codex, or other MCP-enabled agents. Get reliable,
cited answers about timing, patterns, DPS, PMU, and test flows without leaving
your IDE.

**Built for:** Test engineers using AI coding assistants, teams maintaining ATE
test programs (TDC, SmarTest, V93000), and anyone with authorized local ATE
documentation who needs grounded, cited answers.

---

## Quick Start (15–30 min)

```bash
# 1. Install dependencies
uv sync

# 2. Start Qdrant server
docker compose up -d qdrant

# 3. Download embedding models
#    Option A: use the pre-packaged cache (~6.4 GB)
#    Download from PikPak and unzip into the project root:
#    https://mypikpak.com/s/VOuGT6UlblOdQSw2ZNEP9F12o2
#    Option B: let Hugging Face download on first use
#    (temporarily set local_files_only: false in configs/config.yaml)
uv run python scripts/verify_models.py

# 4. Prepare local authorized Markdown documents
mkdir -p data/raw/markdown/v93000/smt7
# Copy or generate your own authorized Markdown files into data/raw/markdown/

# 5. Ingest documents (first run is full; subsequent runs use --incremental)
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown

# 6. Configure your agent to use the MCP server and ATE KB routing policy
uv run python scripts/install_mcp.py --install-agent-policy
# Or see "Agent Integration" below for manual configuration.

# 7. Validate plugin/routing configuration, then restart Codex / Claude Code / Cursor
uv run python scripts/validate_plugin_install.py
uv run python scripts/validate_agent_routing_policy.py

# 8. Start the MCP server (for agent integration)
uv run -m ate_rag_kb.cli.main mcp

# 9. Or start the HTTP API (for direct access)
uv run -m ate_rag_kb.cli.main serve --host 0.0.0.0 --port 8080
```

> **Note:** The model cache (`./embeddings/cache/`) is **not** committed to git
> due to its large size. Ingestion creates local state under `data/processed/`
> and `data/qdrant_server/`; these generated files are also not committed.
>
> **Server mode is the default.** By default the KB connects to
> `http://localhost:6333` (Qdrant server). Local file mode
> (`./data/qdrant_storage/`) is available for single-process development only
> and will trigger `portalocker.AlreadyLocked` if multiple processes access it
> simultaneously.

---

## Model Cache and Offline Mode

The default config runs in offline/cache-only mode:

```yaml
embedding:
  cache_dir: "${ATE_KB_MODEL_CACHE:-./embeddings/cache}"
  local_files_only: true
```

Required cached models:

- `BAAI/bge-m3` for embeddings
- `BAAI/bge-reranker-v2-m3` for cross-encoder reranking

**Download pre-packaged model cache (~6.4 GB):**

If you don't want to download models from Hugging Face manually, use the
pre-packaged cache archive:

1. Download from [PikPak](https://mypikpak.com/s/VOuGT6UlblOdQSw2ZNEP9F12o2)
2. Unzip `ate-kb-model-cache.zip` into the project root
3. Verify with `uv run python scripts/verify_models.py`

The archive contains the full Hugging Face cache layout
(`models--BAAI--bge-m3` and `models--BAAI--bge-reranker-v2-m3`) ready to use
with `local_files_only: true`.

Set a shared or external cache directory when useful:

```bash
export ATE_KB_MODEL_CACHE=/path/to/ate-kb-model-cache
```

Windows PowerShell:

```powershell
$env:ATE_KB_MODEL_CACHE="D:\ate-kb-model-cache"
```

### Local Mode (Single-Process Dev Only)

If you need local mode for quick debugging, set `mode: local` in
`configs/config.yaml`:

```yaml
vector_store:
  mode: local
  local_path: "./data/qdrant_storage"
```

> **Warning:** Local mode locks the storage directory. Only one process can
> access it at a time. Do **not** use local mode when running MCP + CLI + API
> concurrently.

---

## Adding Documents

Use only documents that you are authorized to ingest and query. The repository
does not grant rights to third-party ATE documentation.

**Canonical ATE terminology:**

| Vendor | Tester platform | Software |
|---|---|---|
| Advantest | V93000 | SMT7, SMT8 |
| Teradyne | J750 | IG-XL |

V93000 and J750 are tester platforms. SMT7, SMT8, and IG-XL are software
scopes used for ingestion, retrieval routing, and citation isolation.

If you already have Markdown files, place them under the canonical scope path:

```
data/raw/
├── markdown/
│   ├── v93000/smt7/   # V93000 / SmarTest 7 documents
│   ├── v93000/smt8/   # V93000 / SmarTest 8 documents
│   └── igxl/          # J750 / IG-XL documents
├── json/
│   ├── v93000/smt7/   # optional metadata sidecars for SMT7
│   ├── v93000/smt8/   # optional metadata sidecars for SMT8
│   └── igxl/          # optional metadata sidecars for IG-XL
└── assets/
    ├── v93000/smt7/   # optional local images for SMT7 docs
    ├── v93000/smt8/   # optional local images for SMT8 docs
    └── igxl/          # optional local images for IG-XL docs
```

Then run ingestion:

```bash
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental
```

### Using a Local Conversion Script

You can provide a local script that converts documentation you are allowed to
use into Markdown. Keep vendor-specific conversion scripts outside the public
repository, or place private scripts under `scripts/local/`, which is ignored by
git.

For TDC/Eclipse Help and IG-XL help sources, use the companion converter
project: [ate-help-converters](https://github.com/WalterLuo/ate-help-converters).
It provides macOS and Windows one-click installers plus CLI commands for
converting authorized local help files into Markdown/JSON/assets.

Do not commit converted Markdown, extracted assets, generated JSON sidecars, or
vector database snapshots unless you have explicit redistribution rights.

---

## Agent Integration

### Multi-Harness Plugin Installation (Recommended)

ATE RAG KB can be installed as a plugin in multiple AI CLI tools. Each harness
has its own manifest and installation path. Run the automatic MCP installer to
configure all detected tools:

```bash
# Configure all detected AI CLI tools
uv run python scripts/install_mcp.py --install-agent-policy

# Dry-run first to preview changes
uv run python scripts/install_mcp.py --dry-run

# Configure only specific tools
uv run python scripts/install_mcp.py --harness claude,cursor

# Configure MCP only, without global agent policy (not recommended for projectless sessions)
uv run python scripts/install_mcp.py --skip-agent-policy
```

#### Per-Harness Quick Install

| Harness | Install Command |
|---------|-----------------|
| **Claude Code** | `/plugin install ate-rag-kb@git+https://github.com/walter-luo/ate-rag-kb.git` |
| **Cursor** | `/add-plugin ate-rag-kb` |
| **Codex** | `/plugins` → search "ate-rag-kb" |
| **Gemini CLI** | `gemini extensions install https://github.com/walter-luo/ate-rag-kb.git` |
| **OpenCode** | Add `"ate-rag-kb@git+https://github.com/walter-luo/ate-rag-kb.git"` to `opencode.json` plugins |
| **Copilot CLI** | `copilot plugin install ate-rag-kb@ate-rag-kb-marketplace` |

For detailed per-harness instructions, troubleshooting, and architecture notes,
see [docs/PLUGIN_INSTALL.md](docs/PLUGIN_INSTALL.md).

For local or team Codex marketplace installs, register this repository's
`.agents/plugins/marketplace.json` and then search for `ate-rag-kb`. Public
Codex marketplace search requires publishing or registering the marketplace
outside this repository.

### Claude Code (MCP — Manual Config)

If you prefer manual configuration, add to `~/.claude/settings.json`
(macOS / Linux) or `%USERPROFILE%\.claude\settings.json` (Windows):

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

### Default Agent Behavior

When an engineer asks an ATE technical question, the agent should use MCP tools
first and choose the retrieval strategy itself. The normal path is
`ate_kb.retrieve` or `ate_kb.ask`, followed by `ate_kb.get_document` only when a
full source document is needed. CLI search, grep, and manual markdown reads are
fallbacks for unavailable or insufficient MCP results, not the default workflow.

Configuring an MCP server does not by itself guarantee the model will call MCP
first. In Codex, `ate_kb` may be a deferred tool that must be exposed through
`tool_search`. The recommended installer command,
`uv run python scripts/install_mcp.py --install-agent-policy`, installs a
managed ATE KB Routing policy in addition to MCP configuration. This matters
especially for Codex projectless sessions. If you run `--skip-agent-policy`,
projectless sessions may not reliably prefer `ate_kb`.

After installation, restart your agent and run:

```bash
uv run python scripts/validate_plugin_install.py
uv run python scripts/validate_agent_routing_policy.py
```

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
page through large documents rather than fetching all chunks at once. The MCP
handler uses a paged retrieval path internally, so large documents do not need
to be loaded in full for the first page.

---

## Project Architecture

```
Markdown + JSON  ->  IngestionPipeline  ->  Chunks  ->  EmbeddingEncoder
                                                            |
                                                            v
FastAPI / MCP  <-  RetrievalCoordinator  <-  RetrievalPipeline  <-  QdrantVectorStore  <-  Vectors
```

**RetrievalPipeline stages:**

1. **HybridRetriever** — dense + sparse vector search with Reciprocal Rank Fusion
2. **DocumentGraphExpander** (optional) — follows internal document links
3. **Reranker** — cross-encoder (`BAAI/bge-reranker-v2-m3`)
4. **BroadConceptAssembler** (optional) — coverage-aware selection for broad queries
5. **ParentChildExpander** — enriches with parent/sibling context
6. **ContextCompressor** — deduplicates, merges adjacent, token-caps

For advanced configuration options (chunking strategies, retrieval parameters,
state isolation, migration from local mode), see [CLAUDE.md](CLAUDE.md).

---

## Evaluation & Validation

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

Before using the KB with real engineers, run:

1. [Agent E2E Validation](docs/agent_e2e_validation.md) — step-by-step verification
2. [Beta Checklist](docs/beta_checklist.md) — 10-question trial with pass criteria
3. [Beta 10-Question Trial Report](docs/archive/beta_test_report_10q.md) — archived first trial result
4. [Beta 10-Question Retest Plan](docs/archive/beta_retest_10q.md) — archived post-fix retest procedure

Current beta status: ready for engineer handoff. The first recorded trial
passed 9/10 questions. After the ARRAY citation fix, expected-answer checklist
updates, and paginated `get_document` implementation, the first five priority
questions were retested and passed; evidence is recorded in
[docs/archive/10q_retest.csv](docs/archive/10q_retest.csv).

---

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

The application code is released under the MIT License. See [LICENSE](LICENSE).

Third-party ATE vendor documentation, converted documentation, extracted
assets, model files, and generated vector stores are not included in this
license. See [THIRD_PARTY.md](THIRD_PARTY.md) for redistribution notes.
