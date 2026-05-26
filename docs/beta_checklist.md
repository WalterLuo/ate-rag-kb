# Beta Trial Checklist

Use this checklist when onboarding engineers to the ATE RAG Knowledge Base.

---

## A. Environment Preparation

- [ ] Python / `uv` is installed
- [ ] `uv sync` completed without errors
- [ ] `configs/config.yaml` exists
- [ ] `data/raw/markdown/` contains built-in documents
- [ ] Ingestion has been run at least once
- [ ] `data/qdrant_storage/` exists
- [ ] `uv run -m ate_rag_kb.cli.main status` returns `ok` with `total_chunks > 0`

---

## B. MCP Configuration

- [ ] Copied `.mcp.example.json` to `.mcp.json` (or configured agent MCP directly)
- [ ] Replaced `/path/to/ate-rag-kb` with the absolute project path
- [ ] `CONFIG_PATH` uses an absolute path
- [ ] Agent was restarted after MCP configuration
- [ ] Agent can see all `ate_kb.*` tools
- [ ] `ate_kb.status` returns `ok`

---

## C. Basic Query Validation

Ask the agent the following 10 questions. For each, verify:

1. The agent used an MCP tool
2. The answer is relevant
3. The answer includes `source_md`
4. The answer includes `section_title` or `doc_title`
5. No obvious hallucination

### Questions

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

### Checklist

| # | Question | MCP Used | Relevant | `source_md` | `section_title` | No Hallucination | Pass |
|---|----------|----------|----------|-------------|-----------------|------------------|------|
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

## D. Pagination Verification

- [ ] Agent can first `retrieve` / `ask` to discover `source_md`
- [ ] Agent can call `get_document` and uses a `limit` parameter
- [ ] Response includes `has_more` and `next_offset`
- [ ] Agent does **not** fetch the entire large document in a single call

---

## E. Low-Confidence Verification

- [ ] For an obviously off-topic question, the agent states uncertainty
- [ ] Agent does **not** fabricate APIs, commands, or error codes
- [ ] Agent suggests a more specific query when results are poor

---

## F. Failure Log Template

Record any failures here:

| Question | Expected | Actual | Pass? | Failure Type | Notes |
|----------|----------|--------|-------|--------------|-------|
| | | | | | |

### Failure Types

- `retrieval_miss` — No relevant chunks returned
- `wrong_source` — Citation points to unrelated document
- `no_citation` — Answer lacks `source_md` / `section_title` / `chunk_id`
- `hallucination` — Agent invented facts not in the KB
- `tool_error` — MCP tool call failed or returned an error
- `payload_too_large` — `get_document` returned excessive data
- `slow_response` — Response took an unreasonably long time
- `unclear_answer` — Answer is vague or does not address the question

---

## G. Beta Pass Criteria

Beta is **approved** when all of the following are met:

- [ ] At least 8 out of 10 questions produce usable answers
- [ ] Every usable answer includes proper citations (`source_md`, `section_title`)
- [ ] No serious hallucinations observed
- [ ] MCP tool calls are stable (no repeated JSON-RPC errors)
- [ ] `get_document` never returns an oversized payload
- [ ] Any failures are documented in the Failure Log above
