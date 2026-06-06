"""RAG search tool — semantic search over tenant-scoped documents."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolResult
from app.core.exceptions import EmbeddingError
from app.core.security_context import SecurityContext
from app.rag.embeddings import OllamaEmbeddingProvider
from app.rag.repository import DocumentChunkRepository

logger = logging.getLogger(__name__)

_NAME = "rag_search"


class RAGSearchTool(BaseTool):
    """Search indexed documents using nomic-embed-text semantic similarity."""

    def __init__(
        self, embedding_provider: OllamaEmbeddingProvider | None = None
    ) -> None:
        self._embedder = embedding_provider or OllamaEmbeddingProvider()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=_NAME,
            description=(
                "Search indexed documents for relevant information using semantic "
                "similarity. Returns excerpts and source citations. Use when the "
                "user asks about document content, policies, or knowledge stored "
                "in the knowledge base."
            ),
            parameters=[
                ToolParameter(
                    "query", "string", "Natural language search query", required=True
                ),
                ToolParameter(
                    "project_id",
                    "string",
                    "UUID of the project to search within",
                    required=True,
                ),
                ToolParameter(
                    "top_k",
                    "integer",
                    "Number of results (1-10, default 3)",
                    required=False,
                    default=3,
                ),
            ],
            required_permission="rag.search",
        )

    async def execute(
        self,
        params: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> ToolResult:
        query: str = str(params.get("query", "")).strip()
        project_id_str: str = str(params.get("project_id", "")).strip()
        top_k: int = min(max(int(params.get("top_k", 3)), 1), 10)

        if not query:
            return ToolResult(success=False, data=None, error="query is required")
        if not project_id_str:
            return ToolResult(success=False, data=None, error="project_id is required")
        if "rag.search" not in ctx.permissions:
            return ToolResult(
                success=False, data=None, error="Permission 'rag.search' required"
            )

        try:
            project_id = UUID(project_id_str)
        except ValueError:
            return ToolResult(
                success=False, data=None, error="project_id must be a valid UUID"
            )

        try:
            query_embedding = await self._embedder.embed(query)
        except EmbeddingError as exc:
            return ToolResult(
                success=False, data=None, error=f"Embedding failed: {exc.message}"
            )

        repo = DocumentChunkRepository(session)
        pairs = await repo.search_similar(
            tenant_id=ctx.tenant_id,
            project_id=project_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        results = [
            {
                "citation": chunk.citation_label,
                "filename": filename,
                "excerpt": chunk.content[:500],
            }
            for chunk, filename in pairs
        ]

        logger.debug(
            "tool.rag_search tenant=%s project=%s query_chars=%d results=%d",
            ctx.tenant_id,
            project_id,
            len(query),
            len(results),
        )
        return ToolResult(
            success=True, data={"results": results, "count": len(results)}
        )
