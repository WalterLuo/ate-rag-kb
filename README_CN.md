# ATE RAG 知识库

> **你的编码助手在 ATE 平台上的长期记忆。**

直接在 Claude Code、OpenClaw、Codex 或 Cursor 中查询 TDC/SmarTest 技术文档、API、错误代码和调试流程。获取关于时序、pattern、DPS、PMU 和测试流程的可靠、带引用的答案 —— 无需离开 IDE。

---

## 内置文档

本仓库已内置 **预解析的 TDC/SmarTest 技术文档**。你无需寻找、转换或格式化任何文档 —— 所有文档已放置在 `./data/raw/markdown/` 目录下。

**内置文档覆盖：**

| 平台 | 版本 | 内容 |
|------|------|------|
| ADVANTEST V93000 | SmarTest 7.4.3 / 7.10.11 | PinConfig、Level、Timing、Test Flow、SmartRDI、TML、DPS、PMU、Digital、TMU、RF |

**首次使用（约需 15-30 分钟）：**

```bash
# 1. 安装依赖
uv sync

# 2. 启动 Qdrant 服务器（见下方 Qdrant 服务器配置）
docker compose up -d qdrant

# 3. 下载 Embedding 模型（bge-m3，约 2.2 GB）
#    自动缓存到 ./embeddings/cache/

# 4. 导入内置文档到 Qdrant
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown

# 5. 启动 MCP 服务器并接入你的智能体
uv run -m ate_rag_kb.cli.main mcp
```

> **注意：** Embedding 模型缓存（`./embeddings/cache/`）因体积较大，**未**提交到 git。克隆后需执行一次上述导入步骤。
>
> **Server mode 为默认配置。** 默认情况下 KB 连接到 `http://localhost:6333`
>（Qdrant 服务器）。Local file mode（`./data/qdrant_storage/`）仅供单进程开发调试使用，
> 多进程同时访问会触发 `portalocker.AlreadyLocked` 错误。

---

## 适用人群

- 使用 Claude Code / OpenClaw / Codex / Cursor 的测试工程师
- 维护 ATE 测试程序的团队（TDC、SmarTest、V93000）
- 任何需要关于时序、pattern、DPS、PMU、测试流程和平台 API 的可靠、带引用答案的人

## Qdrant 服务器配置

默认 `configs/config.yaml` 使用 **server mode**（`url: http://localhost:6333`）。
在导入或查询前请先启动 Qdrant：

```bash
# 使用 Docker Compose（推荐）
docker compose up -d qdrant

# 或使用 docker run
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/data/qdrant_server:/qdrant/storage \
  qdrant/qdrant:latest
```

Qdrant 数据持久化到 `./data/qdrant_server/`（与旧的 local mode
`./data/qdrant_storage/` 分开，避免锁冲突）。

### Local Mode（仅限单进程开发）

如需本地模式快速调试，在 `configs/config.yaml` 中设置 `use_local: true`：

```yaml
vector_store:
  use_local: true
  local_path: "./data/qdrant_storage"
```

> 警告：Local mode 会锁定存储目录，同一时间只能有一个进程访问。
> 运行 MCP + CLI + API 并发时**不要**使用 local mode。

## 从 Local Mode 迁移

如果你之前使用 `./data/qdrant_storage/`（local mode）导入了数据，
想切换到 server mode：

1. 启动 Qdrant 服务器（`docker compose up -d qdrant`）。
2. 重新运行导入（server collection 与本地文件相互独立）：
   ```bash
   uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown
   ```
3. 验证：
   ```bash
   uv run -m ate_rag_kb.cli.main status
   ```

没有从本地文件自动迁移到 server collection 的路径；
切换后需要重新导入一次。

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 启动 Qdrant 服务器
docker compose up -d qdrant

# 3. 导入文档（内置文档已位于 ./data/raw/markdown）
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental

# 4. 验证集合状态
uv run -m ate_rag_kb.cli.main status

# 5. 启动 MCP 服务器（用于智能体集成）
uv run -m ate_rag_kb.cli.main mcp

# 6. 或启动 HTTP API（用于直接访问）
uv run -m ate_rag_kb.cli.main serve --host 0.0.0.0 --port 8080
```

## 添加自定义文档

如果你有额外的 Markdown 文件 + JSON 元数据，放置在：

```
data/raw/
├── markdown/     # .md 技术文档（内置文档已在此）
├── json/         # 可选的元数据 sidecar
└── assets/       # 图片、图表
```

然后运行导入：

```bash
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental
```

## Beta 验证

在让工程师正式使用前，请先完成：

1. [Agent 端到端验证](docs/agent_e2e_validation.md) — 逐步验证指南
2. [Beta 试用清单](docs/beta_checklist_CN.md) — 含 10 个真实试用问题及通过标准
3. [Beta 10-Question Trial Report](docs/beta_test_report_10q.md) — 第一次真实工程师试用结果
4. [Beta 10-Question Retest Plan](docs/beta_retest_10q.md) — 修复后的复测流程

当前 Beta 状态：可交付给工程师继续试用。第一次真实试用通过 9/10；在修复
ARRAY 引用、补充预期答案检查点、实现 `get_document` 分页读取后，前 5 个
重点问题已复测通过，证据记录在 [docs/10q_retest.csv](docs/10q_retest.csv)。

开始前复制 MCP 配置示例：

```bash
cp .mcp.example.json .mcp.json
# 编辑 .mcp.json，将 /path/to/ate-rag-kb 替换为项目绝对路径
```

## 智能体集成

### Claude Code（MCP — 推荐）

添加到 `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）或对应位置：

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

重启 Claude Code。智能体将自动发现 `ate_kb.*` 工具。

详细的配置和使用规则，请参阅 [docs/agent_integration.md](docs/agent_integration.md)。

### 默认智能体行为

工程师只需要提出 ATE 技术问题，智能体应自行选择检索策略。默认路径是优先使用
MCP 工具中的 `ate_kb.retrieve` 或 `ate_kb.ask`；只有在已经识别出相关
`source_md` 且需要完整上下文时，才调用 `ate_kb.get_document`。CLI 搜索、
grep、`rg` 和手动读取 markdown 只作为 MCP 不可用或上下文不足时的降级方案，
不应作为默认工作流。

## 可用智能体工具

| 工具 | 描述 | 适用场景 |
|------|------|----------|
| `ate_kb.search` | 快速语义搜索 | 查找相关文档 |
| `ate_kb.retrieve` | 深度检索（含重排序 + 扩展） | 获取全面答案 |
| `ate_kb.ask` | 结构化问答（带引用） | 直接提问 |
| `ate_kb.related` | 查看 chunk 的父/兄弟/子节点 | 需要更广泛的上下文 |
| `ate_kb.get_document` | 分页获取文档 chunks（支持 `limit`/`offset`） | 在发现相关文档后阅读完整参考 |
| `ate_kb.status` | 集合统计信息 | 检查知识库健康状态 |

所有工具都返回结构化 JSON，包含每条结果的 `source_md`、`doc_title`、`section_title`、`chunk_id`、`start_line` 和 `end_line`。

`ate_kb.get_document` 支持分页（`limit`、`offset`）和 `max_tokens` 预算。
智能体在处理大文档时应使用较小的 `limit`（如 20）并逐步翻页，而不是一次性获取所有 chunks。
MCP handler 内部已经使用分页读取路径，因此读取第一页时不需要先加载整篇大文档。

## 评估

运行检索评估：

```bash
uv run python scripts/run_eval.py
```

指标：`hit@k`、`recall@k`、`MRR@k`、`source_precision@k`。

当前基线（50 个问题）：

| 指标 | 数值 |
|------|------|
| `source_precision@5` | 1.0000 |
| `failed_count` | 0 |

## 项目架构

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

## 开发命令

```bash
# 运行测试
uv run pytest tests/ -q

# 运行测试（含覆盖率）
uv run pytest tests/ --cov=src/ate_rag_kb --cov-report=term

# 代码检查
uv run ruff check src/ tests/

# CLI 搜索（开发/调试降级方案）
uv run -m ate_rag_kb.cli.main search "timing set configuration" --top-k 5

# 检查集合统计
uv run -m ate_rag_kb.cli.main status
```

## 许可证

MIT
