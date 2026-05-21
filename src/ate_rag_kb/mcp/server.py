"""MCP server for ATE RAG Knowledge Base.

Provides stdio transport for agent-native integration with Claude Code,
OpenClaw, Codex, and Cursor.
"""

from __future__ import annotations

import json
import logging

from ate_rag_kb.mcp.tools import TOOL_SCHEMAS, McpToolHandler
from ate_rag_kb.retrieval.pipeline import RetrievalPipeline
from ate_rag_kb.utils.config import Config

logger = logging.getLogger(__name__)

_TOOL_DESCRIPTIONS: dict[str, str] = {
    "ate_kb.search": (
        "Quick semantic search over the ATE knowledge base. "
        "Use when exploring a topic or finding relevant source files."
    ),
    "ate_kb.retrieve": (
        "Advanced retrieval with hybrid search, reranking, parent-child expansion, "
        "and compression. Use when answering specific technical questions."
    ),
    "ate_kb.ask": (
        "Structured Q&A with citations and confidence scoring. "
        "Returns grounded context package for agent synthesis."
    ),
    "ate_kb.related": (
        "Get parent, sibling, and child chunks for a given chunk ID. "
        "Use when a retrieved passage needs broader context."
    ),
    "ate_kb.get_document": (
        "Retrieve all chunks for a source markdown file. "
        "Use when reading a complete document or API reference."
    ),
    "ate_kb.status": (
        "Check knowledge base health and collection statistics. "
        "Use to verify the KB is available before querying."
    ),
}


async def run_mcp_server(config: Config) -> None:
    """Run the MCP server with stdio transport.

    This function blocks until the input stream is closed.
    """
    try:
        import mcp.types as types
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
    except ImportError as exc:
        logger.error("MCP SDK not installed: %s", exc)
        raise

    pipeline = RetrievalPipeline(config)
    handler = McpToolHandler(pipeline)

    server = Server("ate-kb")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        tools = []
        for name, schema in TOOL_SCHEMAS.items():
            tools.append(
                types.Tool(
                    name=name,
                    description=_TOOL_DESCRIPTIONS.get(name, ""),
                    inputSchema=schema,
                )
            )
        return tools

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        args = arguments or {}
        logger.info("MCP tool call: %s", name)

        try:
            if name == "ate_kb.search":
                result = await handler.handle_search(args)
            elif name == "ate_kb.retrieve":
                result = await handler.handle_retrieve(args)
            elif name == "ate_kb.ask":
                result = await handler.handle_ask(args)
            elif name == "ate_kb.related":
                result = await handler.handle_related(args)
            elif name == "ate_kb.get_document":
                result = await handler.handle_get_document(args)
            elif name == "ate_kb.status":
                result = await handler.handle_status(args)
            else:
                error_payload = {
                    "error": f"Unknown tool: {name}",
                    "suggestion": "Use ate_kb.search, ate_kb.retrieve, ate_kb.ask, "
                    "ate_kb.related, ate_kb.get_document, or ate_kb.status",
                }
                return [types.TextContent(type="text", text=json.dumps(error_payload, indent=2))]

            return [types.TextContent(type="text", text=result.model_dump_json(indent=2))]

        except Exception as exc:
            logger.exception("MCP tool %s failed", name)
            error_payload = {
                "error": f"Tool execution failed: {exc}",
                "tool": name,
                "suggestion": "Check that Qdrant is running and documents are ingested.",
            }
            return [types.TextContent(type="text", text=json.dumps(error_payload, indent=2))]

    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP server starting (stdio transport)")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
