# ATE RAG 知识库

[English](README.md) | [中文](README_CN.md)

> **你的编码助手在 ATE 平台上的长期记忆。**

直接在 Claude Code、Cursor、Codex 或其他支持 MCP 的智能体中查询 ATE 技术文档、API、错误代码和调试流程。获取关于时序、pattern、DPS、PMU 和测试流程的可靠、带引用的答案，无需离开 IDE。

**适用人群：** 使用 AI 编码助手的测试工程师、维护 ATE 测试程序的团队（V93000、J750），以及任何拥有本地授权 ATE 文档并需要 grounded、带引用答案的人。

---

## 快速开始（15–30 分钟）

```bash
# 1. 安装依赖
uv sync

# 2. 启动 Qdrant 服务器
docker compose up -d qdrant

# 3. 下载 Embedding 模型
#    方案 A：使用预打包缓存（约 6.4 GB）
#    从 PikPak 下载并解压到项目根目录：
#    https://mypikpak.com/s/VOuGT6UlblOdQSw2ZNEP9F12o2
#    方案 B：首次使用时让 Hugging Face 自动下载
#    （临时在 configs/config.yaml 中设置 local_files_only: false）
uv run python scripts/verify_models.py

# 4. 准备本地授权 Markdown 文档
mkdir -p data/raw/markdown/v93000/smt7
# 将你有权使用的 Markdown 文件复制或生成到 data/raw/markdown/

# 5. 导入文档（首次为全量；后续运行加 --incremental）
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown

# 6. 配置智能体使用 MCP server 和 ATE KB 路由策略
uv run python scripts/install_mcp.py --install-agent-policy
# 或查看下方"智能体集成"了解手动配置。

# 7. 验证插件/路由配置，然后重启 Codex / Claude Code / Cursor
uv run python scripts/validate_plugin_install.py
uv run python scripts/validate_agent_routing_policy.py

# 8. 启动 MCP 服务器（用于智能体集成）
uv run -m ate_rag_kb.cli.main mcp

# 9. 或启动 HTTP API（用于直接访问）
uv run -m ate_rag_kb.cli.main serve --host 0.0.0.0 --port 8080
```

> **注意：** 模型缓存（`./embeddings/cache/`）因体积较大，**未**提交到 git。
> 导入会在 `data/processed/` 和 `data/qdrant_server/` 下生成本地状态；
> 这些生成文件同样不会提交到 git。
>
> **Server mode 为默认配置。** 默认情况下 KB 连接到 `http://localhost:6333`
>（Qdrant 服务器）。Local file mode（`./data/qdrant_storage/`）仅供单进程开发调试使用，
> 多进程同时访问会触发 `portalocker.AlreadyLocked` 错误。

---

## 模型缓存与离线模式

默认配置使用离线/缓存优先模式：

```yaml
embedding:
  cache_dir: "${ATE_KB_MODEL_CACHE:-./embeddings/cache}"
  local_files_only: true
```

需要的缓存模型：

- `BAAI/bge-m3`：用于 embedding
- `BAAI/bge-reranker-v2-m3`：用于 cross-encoder rerank

**下载预打包模型缓存（约 6.4 GB）：**

如果你不想手动从 Hugging Face 下载模型，可使用预打包的缓存压缩包：

1. 从 [PikPak](https://mypikpak.com/s/VOuGT6UlblOdQSw2ZNEP9F12o2) 下载
2. 将 `ate-kb-model-cache.zip` 解压到项目根目录
3. 运行 `uv run python scripts/verify_models.py` 验证

该压缩包包含完整的 Hugging Face 缓存结构
（`models--BAAI--bge-m3` 和 `models--BAAI--bge-reranker-v2-m3`），可直接配合
`local_files_only: true` 使用。

如果希望把模型缓存放到共享目录或外部磁盘：

```bash
export ATE_KB_MODEL_CACHE=/path/to/ate-kb-model-cache
```

Windows PowerShell：

```powershell
$env:ATE_KB_MODEL_CACHE="D:\ate-kb-model-cache"
```

### Local Mode（仅限单进程开发）

如需本地模式快速调试，在 `configs/config.yaml` 中设置 `mode: local`：

```yaml
vector_store:
  mode: local
  local_path: "./data/qdrant_storage"
```

> **警告：** Local mode 会锁定存储目录，同一时间只能有一个进程访问。
> 运行 MCP + CLI + API 并发时**不要**使用 local mode。

---

## 添加文档

只导入你有权使用和检索的文档。本仓库本身不授予任何第三方 ATE 文档的使用或再分发权利。

**ATE 规范术语：**

| 厂商 | 测试平台 | 软件 |
|---|---|---|
| Advantest | V93000 | SMT7、SMT8 |
| Teradyne | J750 | IG-XL |

V93000 和 J750 是测试平台。SMT7、SMT8、IG-XL 是软件范围，用于导入、检索路由和引用隔离。

如果你已经有 Markdown 文件，请按标准 scope 路径放置：

```
data/raw/
├── markdown/
│   ├── v93000/smt7/   # V93000 / SmarTest 7 文档
│   ├── v93000/smt8/   # V93000 / SmarTest 8 文档
│   └── igxl/          # J750 / IG-XL 文档
├── json/
│   ├── v93000/smt7/   # 可选 SMT7 元数据 sidecar
│   ├── v93000/smt8/   # 可选 SMT8 元数据 sidecar
│   └── igxl/          # 可选 IG-XL 元数据 sidecar
└── assets/
    ├── v93000/smt7/   # 可选 SMT7 本地图片
    ├── v93000/smt8/   # 可选 SMT8 本地图片
    └── igxl/          # 可选 IG-XL 本地图片
```

然后运行导入：

```bash
uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown --incremental
```

### 使用本地转换脚本

你可以提供一个本地脚本，把你有权使用的文档转换为 Markdown。建议将厂商文档相关的私有转换脚本放在公开仓库之外，或放在已被 git 忽略的 `scripts/local/` 目录下。

对于 TDC/Eclipse Help 和 IG-XL 帮助源，推荐使用配套转换器项目：
[ate-help-converters](https://github.com/WalterLuo/ate-help-converters)。
该项目提供 macOS 和 Windows 一键安装脚本，以及用于把本地授权帮助文件转换为
Markdown/JSON/assets 的命令行工具。

除非你拥有明确的再分发授权，否则不要提交转换后的 Markdown、提取图片、生成的 JSON sidecar 或向量数据库快照。

---

## 智能体集成

### 多平台插件安装（推荐）

ATE RAG KB 支持在多种 AI CLI 工具中以插件形式安装。每个工具都有独立的
manifest 和安装路径。运行自动 MCP 安装脚本即可配置所有已检测到的工具：

```bash
# 配置所有检测到的 AI CLI 工具
uv run python scripts/install_mcp.py --install-agent-policy

# 先干跑预览将要修改的内容
uv run python scripts/install_mcp.py --dry-run

# 只配置指定工具
uv run python scripts/install_mcp.py --harness claude,cursor

# 只配置 MCP，不写全局 agent policy（不推荐 projectless 会话使用）
uv run python scripts/install_mcp.py --skip-agent-policy
```

#### 各平台快速安装

| 工具 | 安装命令 |
|---------|-----------------|
| **Claude Code** | `/plugin install ate-rag-kb@git+https://github.com/walter-luo/ate-rag-kb.git` |
| **Cursor** | `/add-plugin ate-rag-kb` |
| **Codex** | `/plugins` → 搜索 "ate-rag-kb" |
| **Gemini CLI** | `gemini extensions install https://github.com/walter-luo/ate-rag-kb.git` |
| **OpenCode** | 在 `opencode.json` 的 plugins 中添加 `"ate-rag-kb@git+https://github.com/walter-luo/ate-rag-kb.git"` |
| **Copilot CLI** | `copilot plugin install ate-rag-kb@ate-rag-kb-marketplace` |

详细的各平台说明、故障排查和架构说明请参阅 [docs/PLUGIN_INSTALL_CN.md](docs/PLUGIN_INSTALL_CN.md)。

Codex 本地/团队 marketplace 可使用本仓库的
`.agents/plugins/marketplace.json` 注册后搜索安装；公共插件市场可搜索安装还需要
后续发布或注册 marketplace。

### Claude Code（MCP — 手动配置）

如果你偏好手动配置，添加到 `~/.claude/settings.json`
（macOS / Linux）或 `%USERPROFILE%\.claude\settings.json`（Windows）：

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

### 默认智能体行为

工程师只需要提出 ATE 技术问题，智能体应自行选择检索策略。默认路径是优先使用
MCP 工具中的 `ate_kb.retrieve` 或 `ate_kb.ask`；只有在已经识别出相关
`source_md` 且需要完整上下文时，才调用 `ate_kb.get_document`。CLI 搜索、
grep、`rg` 和手动读取 markdown 只作为 MCP 不可用或上下文不足时的降级方案，
不应作为默认工作流。

仅配置 MCP server 并不等于 agent 一定会第一时间调用 MCP。Codex 中
`ate_kb` 可能是 deferred tool，需要先通过 `tool_search` 暴露。因此推荐使用
`uv run python scripts/install_mcp.py --install-agent-policy`，它会在 MCP 配置之外
安装全局 ATE KB Routing policy。对于 Codex projectless 会话，这个全局 policy
尤其重要；如果使用 `--skip-agent-policy`，则无法保证不在项目目录中打开的会话会
优先调用 `ate_kb`。

安装后请重启 agent，并运行：

```bash
uv run python scripts/validate_plugin_install.py
uv run python scripts/validate_agent_routing_policy.py
```

## 可用智能体工具

| 工具 | 描述 | 适用场景 |
|------|------|----------|
| `ate_kb.search` | 快速语义搜索 | 查找相关文档 |
| `ate_kb.retrieve` | 深度检索（含重排序 + 扩展） | 获取全面答案 |
| `ate_kb.ask` | 结构化问答（带引用） | 直接提问 |
| `ate_kb.related` | 查看 chunk 的父/兄弟/子节点 | 需要更广泛的上下文 |
| `ate_kb.get_document` | 分页获取文档 chunks（支持 `limit`/`offset`） | 在发现相关文档后阅读完整参考 |
| `ate_kb.status` | 集合统计信息 | 检查知识库健康状态 |

所有工具都返回结构化 JSON，包含每条结果的 `source_md`、`doc_title`、
`section_title`、`chunk_id`、`start_line` 和 `end_line`。

`ate_kb.get_document` 支持分页（`limit`、`offset`）和 `max_tokens` 预算。
智能体在处理大文档时应使用较小的 `limit`（如 20）并逐步翻页，而不是一次性获取所有 chunks。
MCP handler 内部已经使用分页读取路径，因此读取第一页时不需要先加载整篇大文档。

---

## 项目架构

```
Markdown + JSON  ->  IngestionPipeline  ->  Chunks  ->  EmbeddingEncoder
                                                            |
                                                            v
FastAPI / MCP  <-  RetrievalCoordinator  <-  RetrievalPipeline  <-  QdrantVectorStore  <-  Vectors
```

**RetrievalPipeline 阶段：**

1. **HybridRetriever** — dense + sparse 向量搜索，使用 Reciprocal Rank Fusion
2. **DocumentGraphExpander**（可选）— 遍历文档内部链接
3. **Reranker** — cross-encoder（`BAAI/bge-reranker-v2-m3`）
4. **BroadConceptAssembler**（可选）— 宽泛查询的覆盖感知选择
5. **ParentChildExpander** — 补充父/兄弟节点上下文
6. **ContextCompressor** — 去重、合并相邻片段、token 上限控制

高级配置选项（分块策略、检索参数、状态隔离、从 local mode 迁移）请参阅 [CLAUDE.md](CLAUDE.md)。

---

## 评估与验证

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

在让工程师正式使用前，请先完成：

1. [Agent 端到端验证](docs/agent_e2e_validation_CN.md) — 逐步验证指南
2. [Beta 试用清单](docs/beta_checklist_CN.md) — 含 10 个真实试用问题及通过标准
3. [Beta 10-Question Trial Report](docs/archive/beta_test_report_10q.md) — 已归档的第一次真实工程师试用结果
4. [Beta 10-Question Retest Plan](docs/archive/beta_retest_10q.md) — 已归档的修复后复测流程

当前 Beta 状态：可交付给工程师继续试用。第一次真实试用通过 9/10；在修复
ARRAY 引用、补充预期答案检查点、实现 `get_document` 分页读取后，前 5 个
重点问题已复测通过，证据记录在 [docs/archive/10q_retest.csv](docs/archive/10q_retest.csv)。

---

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

应用代码使用 MIT License 发布。请参阅 [LICENSE](LICENSE)。

第三方 ATE 厂商文档、转换后的文档、提取的资源文件、模型文件和生成的向量库不包含在该许可证内。再分发注意事项见
[THIRD_PARTY.md](THIRD_PARTY.md)。
