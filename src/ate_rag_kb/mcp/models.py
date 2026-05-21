"""Pydantic models for MCP tool input/output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class McpChunkResult(BaseModel):
    """A single retrieved chunk with full metadata for MCP tools."""

    id: str = Field(description="Unique chunk ID (SHA256)")
    content: str = Field(description="Full chunk content")
    score: float = Field(description="Relevance score 0-1")
    chunk_type: str = Field(default="paragraph", description="Chunk type")
    doc_title: str = Field(default="", description="Document title")
    section_title: str = Field(default="", description="Section title")
    subsection_title: str = Field(default="", description="Subsection title")
    source_md: str = Field(default="", description="Source markdown file path")
    toc_path: list[str] = Field(default_factory=list, description="TOC hierarchy")
    platform: str = Field(default="", description="Platform (TDC, J750, etc.)")
    doc_type: str = Field(default="", description="Document type")
    heading_level: int = Field(default=0, description="Heading level")
    start_line: int = Field(default=0, description="Start line in source")
    end_line: int = Field(default=0, description="End line in source")
    parent_id: str | None = Field(default=None, description="Parent chunk ID")
    sibling_ids: list[str] = Field(default_factory=list, description="Sibling chunk IDs")
    child_ids: list[str] = Field(default_factory=list, description="Child chunk IDs")
    is_expanded: bool = Field(
        default=False,
        description="True if added via parent/sibling expansion",
    )


class McpCitation(BaseModel):
    """Citation mapping retrieved context to source chunks."""

    chunk_id: str
    excerpt: str = Field(description="300-char excerpt from chunk")
    source_md: str
    toc_path: list[str] = Field(default_factory=list)
    start_line: int = 0
    end_line: int = 0


class McpContextPackage(BaseModel):
    """Pre-formatted context string ready for LLM prompt injection."""

    text: str = Field(description="Concatenated chunk contents with citation markers")
    token_estimate: int = Field(description="Approximate token count")
    citation_map: list[dict] = Field(
        default_factory=list,
        description="Maps citation markers [1], [2] to chunk metadata",
    )


class McpSearchResult(BaseModel):
    """Output for ate_kb.search tool."""

    query: str
    total: int = Field(description="Number of chunks returned")
    chunks: list[McpChunkResult]
    sources: list[dict] = Field(
        default_factory=list,
        description="Unique source files ordered by relevance",
    )


class McpRetrieveResult(BaseModel):
    """Output for ate_kb.retrieve tool."""

    query: str
    total: int
    processing: dict = Field(
        default_factory=dict,
        description="Flags indicating which processing steps ran",
    )
    chunks: list[McpChunkResult]
    context_package: McpContextPackage | None = None


class McpAskResult(BaseModel):
    """Output for ate_kb.ask tool."""

    question: str
    answer: str = Field(
        default="",
        description="Guidance text (LLM synthesis disabled in phase 1)",
    )
    citations: list[McpCitation]
    source_files: list[str] = Field(default_factory=list)
    toc_paths: list[list[str]] = Field(default_factory=list)
    confidence: str = Field(
        default="medium",
        description="high / medium / low based on score distribution",
    )
    context_package: McpContextPackage | None = None


class McpRelatedResult(BaseModel):
    """Output for ate_kb.related tool."""

    chunk_id: str
    parent: McpChunkResult | None = None
    siblings: list[McpChunkResult] = Field(default_factory=list)
    children: list[McpChunkResult] = Field(default_factory=list)


class McpDocumentResult(BaseModel):
    """Output for ate_kb.get_document tool."""

    source_md: str
    total: int
    chunks: list[McpChunkResult]


class McpStatusResult(BaseModel):
    """Output for ate_kb.status tool."""

    status: str = Field(description="ok / degraded / unavailable")
    collection_name: str = ""
    total_chunks: int = 0
    vector_size: int = 0
    embedding_model: str = ""
    platforms: list[str] = Field(default_factory=list)
    doc_types: list[str] = Field(default_factory=list)
    version: str = "0.1.0"
