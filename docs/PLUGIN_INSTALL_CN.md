# ATE RAG KB — 多平台插件安装指南

本文档介绍如何在各种 AI CLI 工具中安装和配置 **ate-rag-kb** 插件或 MCP 扩展。

## 前置条件（所有平台）

在将 ate-rag-kb 安装到任何 AI 工具之前，请先确保项目本身已准备就绪：

1. **Python 3.10+** 并安装 [`uv`](https://docs.astral.sh/uv/)
2. **克隆仓库**并安装依赖：
   ```bash
   git clone https://github.com/WalterLuo/ate-rag-kb.git
   cd ate-rag-kb
   uv sync
   ```
3. **模型**已下载到 `embeddings/cache/`（见 `scripts/package_models.py`）
4. **Qdrant** 正在运行（本地或远程）且文档已导入：
   ```bash
   uv run -m ate_rag_kb.cli.main ingest --dir ./data/raw/markdown
   ```

## 快速设置（推荐）

自动安装程序会为**读取外部 MCP 配置文件的工具——Claude Code、Cursor 和
Codex**配置 MCP server，并安装托管的 ATE KB Routing policy：

```bash
uv run python scripts/install_mcp.py --install-agent-policy
```

> Gemini CLI 和 OpenCode **不**由该脚本处理，它们通过各自的原生机制接入 MCP：
> Gemini 在 `gemini extensions install` 时从 `gemini-extension.json` 的
> `mcpServers` 读取；OpenCode 通过其插件管理器安装（见 `.opencode/INSTALL.md`）。

先干跑查看将要修改的内容：

```bash
uv run python scripts/install_mcp.py --dry-run
```

只配置指定的工具：

```bash
uv run python scripts/install_mcp.py --harness claude,cursor
```

只配置 MCP，不写全局 agent policy：

```bash
uv run python scripts/install_mcp.py --skip-agent-policy
```

这不推荐用于 Codex projectless 会话，因为仓库里的 `AGENTS.md` 可能不会被加载。

---

## 各平台安装方式

### Claude Code

**通过 Marketplace 安装（推荐）：**

```bash
/plugin marketplace add WalterLuo/ate-rag-kb-marketplace
/plugin install ate-rag-kb@ate-rag-kb-marketplace
```

**或直接从本仓库安装：**

```bash
/plugin install ate-rag-kb@git+https://github.com/WalterLuo/ate-rag-kb.git
```

**MCP 配置：**

Claude Code 通过 `settings.json` 支持 MCP server。安装脚本会自动配置，或手动添加：

```json
// ~/.claude/settings.json（全局）或 .claude/settings.json（项目级）
{
  "mcpServers": {
    "ate_kb": {
      "command": "uv",
      "args": ["run", "-m", "ate_rag_kb.cli.main", "mcp"]
    }
  }
}
```

**验证：**

```
What V93000 timing set commands are available?
```

Claude Code 应自动调用 `ate_kb.search` 或 `ate_kb.retrieve`。

---

### Cursor

**从 Marketplace 安装：**

```bash
/add-plugin ate-rag-kb
```

**或搜索安装：**

在 Cursor Agent 聊天中，于插件市场搜索 "ate-rag-kb"。

**MCP 配置：**

Cursor 使用 `.cursor/mcp.json`（项目级）或 `~/.cursor/mcp.json`（全局）：

```json
{
  "mcpServers": {
    "ate_kb": {
      "command": "uv",
      "args": ["run", "-m", "ate_rag_kb.cli.main", "mcp"]
    }
  }
}
```

`scripts/install_mcp.py` 会自动配置此项。

---

### Codex CLI / Codex App

**从 Marketplace 安装：**

```bash
/plugins
# 搜索 "ate-rag-kb" 并选择 Install Plugin。
```

如果是本地或团队 marketplace 测试，先添加本仓库提供的 Codex marketplace
manifest，然后再搜索 `ate-rag-kb`：

```bash
codex plugin marketplace add /path/to/ate-rag-kb/.agents/plugins/marketplace.json
```

如果要进入公共 Codex 插件市场搜索结果，还需要在仓库之外完成 marketplace 发布或注册。

**MCP 配置：**

Codex 同样支持 MCP server。添加到 `~/.codex/settings.json`：

```json
{
  "mcpServers": {
    "ate_kb": {
      "command": "uv",
      "args": ["run", "-m", "ate_rag_kb.cli.main", "mcp"]
    }
  }
}
```

或运行 `scripts/install_mcp.py --harness codex --install-agent-policy`。

安装后重启 Codex，并运行：

```bash
uv run python scripts/validate_plugin_install.py
uv run python scripts/validate_agent_routing_policy.py
```

---

### Gemini CLI

**安装扩展：**

```bash
gemini extensions install https://github.com/WalterLuo/ate-rag-kb.git
```

**后续更新：**

```bash
gemini extensions update ate-rag-kb
```

Gemini CLI 读取仓库根目录的 `gemini-extension.json`。该清单在 `mcpServers` 下声明了 `ate-kb` MCP 服务器（通过 `uv run ... mcp` 启动），并指向 `GEMINI.md` 作为上下文文件。路径使用 `${extensionPath}` 变量，使扩展可在不同机器间移植。安装扩展时会自动接入 MCP 服务器，无需手动编辑 `mcpServers`。

---

### OpenCode

**通过 git-backed 插件安装：**

在你的 `opencode.json`（全局或项目级）中添加：

```json
{
  "plugin": ["ate-rag-kb@git+https://github.com/WalterLuo/ate-rag-kb.git"]
}
```

重启 OpenCode。详细说明请参阅 `.opencode/INSTALL.md`。

---

### GitHub Copilot CLI

**注册 Marketplace：**

```bash
copilot plugin marketplace add WalterLuo/ate-rag-kb-marketplace
```

**安装插件：**

```bash
copilot plugin install ate-rag-kb@ate-rag-kb-marketplace
```

VS Code 中的 Copilot Chat 也可以通过 `~/.vscode/mcp.json` 或工作区设置使用 MCP server。

---

### Factory Droid

**注册 Marketplace：**

```bash
droid plugin marketplace add https://github.com/WalterLuo/ate-rag-kb
droid plugin install ate-rag-kb@ate-rag-kb
```

---

## 插件文件参考

| 工具 | 本仓库中的对应文件 |
|---------|-------------------|
| Claude Code | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` |
| Cursor | `.cursor-plugin/plugin.json` |
| Codex | `.codex-plugin/plugin.json` |
| Gemini CLI | `gemini-extension.json`, `GEMINI.md` |
| OpenCode | `.opencode/INSTALL.md` |
| Claude / Cursor / Codex MCP 安装器 | `scripts/install_mcp.py` |

## 故障排查

### MCP server 无法启动

1. 在项目根目录下手动运行 `uv run -m ate_rag_kb.cli.main mcp` 验证是否正常。
2. 检查 `embeddings/cache/` 中模型是否存在。
3. 确保 Qdrant 可访问（检查 `configs/config.yaml`）。

### 插件未加载

1. 确认插件 manifest 的 JSON 语法有效。
2. 检查 AI 工具的日志中是否有插件加载错误。
3. 对于 Marketplace 安装，确认 Marketplace URL 可访问。

### 模型缓存错误

如果看到 "Local model cache not found"，说明 embedding 模型缺失。解压模型压缩包或重新下载：

```bash
# 将 ate-rag-kb-models.zip 解压到项目根目录后
uv run python scripts/verify_models.py
```

## 架构说明

- **MCP 优先：** 所有支持 MCP 的工具（Claude Code、Cursor、Codex、Copilot Chat）都连接到同一个 `ate_rag_kb.cli.main mcp` stdio server。
- **路由 skill：** `skills/ate-kb-router/SKILL.md` 让支持 skill 的 agent 在 web 或 shell 降级前先暴露并调用 `ate_kb`。
- **托管 policy：** `scripts/install_mcp.py --install-agent-policy` 会追加或更新全局 agent 指令中的 ATE KB Routing 块，不覆盖用户原有规则。
- **上下文文件：** `CLAUDE.md`、`GEMINI.md` 和 `AGENTS.md` 提供各工具专属指令，让 AI 知道如何使用 `ate_kb` 工具。
- **插件清单：** 每个工具在专属目录中维护自己的 manifest 格式（`.claude-plugin/`、`.cursor-plugin/`、`.codex-plugin/`）。
