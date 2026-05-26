# Beta 试用清单

工程师试用 ATE RAG 知识库时的逐项检查表。

---

## A. 环境准备

- [ ] 已安装 Python / uv
- [ ] `uv sync` 已完成且无报错
- [ ] `configs/config.yaml` 存在
- [ ] `data/raw/markdown/` 中包含内置文档
- [ ] 已至少运行过一次 ingest
- [ ] `data/qdrant_storage/` 存在
- [ ] `uv run -m ate_rag_kb.cli.main status` 返回 `ok` 且 `total_chunks > 0`

---

## B. MCP 配置

- [ ] 已复制 `.mcp.example.json` 为 `.mcp.json`（或直接在 agent 中配置了 MCP）
- [ ] 已将 `/path/to/ate-rag-kb` 替换为项目绝对路径
- [ ] `CONFIG_PATH` 使用了绝对路径
- [ ] 配置后已重启 agent
- [ ] Agent 能看到全部 `ate_kb.*` 工具
- [ ] `ate_kb.status` 返回 `ok`

---

## C. 基础查询验证

向 agent 提出以下 10 个问题，每个问题检查：

1. Agent 使用了 MCP 工具
2. 回答内容相关
3. 回答包含 `source_md`
4. 回答包含 `section_title` 或 `doc_title`
5. 没有明显幻觉

### 问题列表

1. How to configure drive edge in TDC?
2. What is the difference between drive edge and compare edge?
3. How to create a new timeset?
4. How to enable burst pattern mode?
5. How to debug pattern miscompare?
6. What does DPS alarm 2034 mean?
7. How to configure voltage clamp?
8. How to configure PMU force current mode?
9. How does flow bypass work?
10. How to share variables between test methods?

### 检查表

| 序号 | 问题 | 使用 MCP | 内容相关 | 含 source_md | 含 section_title | 无幻觉 | 通过 |
|------|------|----------|----------|--------------|------------------|--------|------|
| 1 | How to configure drive edge in TDC? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 2 | What is the difference between drive edge and compare edge? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3 | How to create a new timeset? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4 | How to enable burst pattern mode? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5 | How to debug pattern miscompare? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 6 | What does DPS alarm 2034 mean? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 7 | How to configure voltage clamp? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 8 | How to configure PMU force current mode? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 9 | How does flow bypass work? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 10 | How to share variables between test methods? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

---

## D. 分页验证

- [ ] Agent 能先通过 `retrieve` / `ask` 找到 `source_md`
- [ ] Agent 能调用 `get_document` 并使用 `limit` 参数
- [ ] 返回结果包含 `has_more` 和 `next_offset`
- [ ] Agent 不会一次性读取整篇大文档

---

## E. 低置信度验证

- [ ] 对于明显无关的问题，agent 会说明不确定
- [ ] Agent 不会编造不存在的 API、命令或错误码
- [ ] 当结果较差时，agent 会建议更具体的查询方式

---

## F. 失败记录模板

在此处记录所有失败案例：

| 问题 | 期望结果 | 实际结果 | 是否通过 | 失败类型 | 备注 |
|------|----------|----------|----------|----------|------|
| | | | | | |

### 失败类型说明

- `retrieval_miss` — 未返回相关 chunk
- `wrong_source` — 引用指向了无关文档
- `no_citation` — 回答缺少 `source_md` / `section_title` / `chunk_id`
- `hallucination` — Agent 编造了知识库中不存在的事实
- `tool_error` — MCP 工具调用失败或返回错误
- `payload_too_large` — `get_document` 返回了过量数据
- `slow_response` — 响应时间异常长
- `unclear_answer` — 回答模糊或未回答问题

---

## G. Beta 通过标准

满足以下全部条件时，Beta 试用通过：

- [ ] 10 个问题中至少 8 个产生可用回答
- [ ] 每个可用回答都包含规范引用（`source_md`、`section_title`）
- [ ] 未观察到严重幻觉
- [ ] MCP 工具调用稳定（无频繁 JSON-RPC 错误）
- [ ] `get_document` 未返回超大 payload
- [ ] 所有失败案例已记录在上方的失败日志中
