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
   at once.
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
