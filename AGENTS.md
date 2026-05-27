# Agent Operating Policy

This repository is an ATE knowledge-base system for test engineers. Engineers
should be able to ask domain questions directly, without deciding which search
or retrieval command an agent should run.

## ATE KB Question Policy

When a user asks any technical or business question about ATE documentation,
SmarTest, TDC, V93000, pin configuration, timing, levels, patterns, DPS, PMU,
test flow, tester behavior, command syntax, or API references:

1. Use MCP tools first.
2. Prefer `ate_kb.retrieve` for answering specific technical questions.
3. Prefer `ate_kb.ask` when the user asks a direct question and needs citations.
4. Use `ate_kb.get_document` only after relevant `source_md` files are
   identified by `ate_kb.retrieve` or `ate_kb.ask`. Prefer pagination
   (`limit`, `offset`) for large documents rather than fetching all chunks
   at once. Use small limits such as 10 or 20 for large references.
5. Use `ate_kb.search` only for exploratory discovery or when locating source
   files.
6. Do not use `uv run -m ate_rag_kb.cli.main search`, shell `grep`, `rg`, or
   manual raw markdown reads as the first step for ATE KB questions.
7. Fall back to CLI, file search, or raw markdown reads only when MCP tools are
   unavailable, fail, or return insufficient context.
8. Do not ask the engineer which retrieval method to use. Select the retrieval
   strategy yourself.
9. Cite `source_md`, `section_title`, and command/document names in final
   answers when the answer comes from the KB.

Default flow:

```text
User asks ATE question
-> call ate_kb.retrieve or ate_kb.ask
-> inspect citations and context_package
-> call ate_kb.get_document with limit/offset only if full-document context is needed
-> synthesize the answer with citations
```

The CLI search command is a developer/debugging fallback. It returns only a
short content preview and should not be treated as the normal agent interface.

## Beta Retest Policy

The current beta acceptance flow is documented in:

- `docs/beta_checklist_CN.md`
- `docs/beta_test_report_10q.md`
- `docs/beta_retest_10q.md`

For ARRAY questions, verify that final answers cite ARRAY-specific sources such
as `20847.md`, `130224.md`, or `102025.md`. For large documents, verify that
the agent uses `ate_kb.get_document` with explicit `limit` / `offset`.
