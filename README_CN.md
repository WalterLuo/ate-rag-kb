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

# 2. 下载 Embedding 模型（bge-m3，约 2.2 GB）
#    自动缓存到 ./embeddings/cache/

# 3. 导入内置文档并生成向量数据库
#    向量存储在 ./data/qdrant_storage/
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown

# 4. 启动 MCP 服务器并接入你的智能体
uv run -m ate_rag_kb.cli.main mcp
```

> **注意：** 向量数据库（`./data/qdrant_storage/`）和 Embedding 模型缓存（`./embeddings/cache/`）因体积较大，**未**提交到 git。克隆后需执行一次上述导入步骤。

---

## 适用人群

- 使用 Claude Code / OpenClaw / Codex / Cursor 的测试工程师
- 维护 ATE 测试程序的团队（TDC、SmarTest、V93000）
- 任何需要关于时序、pattern、DPS、PMU、测试流程和平台 API 的可靠、带引用答案的人

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 导入文档（内置文档已位于 ./data/raw/markdown）
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental

# 3. 启动 MCP 服务器（用于智能体集成）
uv run -m ate_rag_kb.cli.main mcp

# 4. 或启动 HTTP API（用于直接访问）
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

## 可用智能体工具

| 工具 | 描述 | 适用场景 |
|------|------|----------|
| `ate_kb.search` | 快速语义搜索 | 查找相关文档 |
| `ate_kb.retrieve` | 深度检索（含重排序 + 扩展） | 获取全面答案 |
| `ate_kb.ask` | 结构化问答（带引用） | 直接提问 |
| `ate_kb.related` | 查看 chunk 的父/兄弟/子节点 | 需要更广泛的上下文 |
| `ate_kb.get_document` | 获取完整文档的所有 chunks | 阅读完整参考资料 |
| `ate_kb.status` | 集合统计信息 | 检查知识库健康状态 |

所有工具都返回结构化 JSON，包含每条结果的 `source_md`、`doc_title`、`section_title`、`chunk_id`、`start_line` 和 `end_line`。

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

# CLI 搜索
uv run -m ate_rag_kb.cli.main search "timing set configuration" --top-k 5

# 检查集合统计
uv run -m ate_rag_kb.cli.main status
```

## 许可证

MIT
