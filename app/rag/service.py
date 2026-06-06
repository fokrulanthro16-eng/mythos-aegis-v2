"""RAG service layer.

Orchestrates: upload → chunk → embed → store → search → ask.

Security invariants:
- Document content is NEVER written to any log.
- Raw embeddings are NEVER returned in API responses.
- tenant_id is ALWAYS sourced from the validated SecurityContext.
- All DB queries are scoped to tenant_id + project_id.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_gateway.providers.ollama_provider import OllamaProvider
from app.core.exceptions import (
    AIProviderUnavailableError,
    AuthorizationError,
    EmbeddingError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.core.result import Failure, Result, Success
from app.core.security_context import SecurityContext
from app.db.models.document import DocumentStatus
from app.db.models.document_chunk import DocumentChunk
from app.rag.chunker import chunk_text, content_hash, estimate_tokens, extract_text
from app.rag.citation import build_citations, make_citation_label
from app.rag.embeddings import OllamaEmbeddingProvider
from app.rag.repository import DocumentChunkRepository, DocumentRepository
from app.rag.schemas import (
    AskRequest,
    AskResponse,
    ChunkResult,
    Citation,
    DocumentListItem,
    DocumentUploadResponse,
    SearchRequest,
    SearchResponse,
)
from app.saas.repository import UsageRepository

logger = logging.getLogger(__name__)

_PERM_UPLOAD = "rag.upload"
_PERM_SEARCH = "rag.search"
_PERM_ASK = "rag.ask"

# Prompt template — never logs the content strings themselves.
_ASK_PROMPT_TEMPLATE = """\
You are a helpful assistant. Answer the following question using only the \
provided context. If the context does not contain enough information, say so.

Context:
---
{context}
---

Question: {question}

Answer:"""

_ASK_MAX_TOKENS = 1024


def _billing_period(dt: datetime | None = None) -> str:
    return (dt or datetime.now(UTC)).strftime("%Y-%m")


class RAGService:
    """Orchestrate the RAG pipeline with tenant/project isolation."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: OllamaEmbeddingProvider | None = None,
        answer_provider: OllamaProvider | None = None,
    ) -> None:
        self._session = session
        self._embedder = embedding_provider or OllamaEmbeddingProvider()
        self._answerer = answer_provider or OllamaProvider()
        self._docs = DocumentRepository(session)
        self._chunks = DocumentChunkRepository(session)
        self._usage = UsageRepository(session)

    # ── upload ────────────────────────────────────────────────────────────────

    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        project_id: UUID,
        ctx: SecurityContext,
    ) -> Result[DocumentUploadResponse]:
        """Parse, chunk, embed, and index a document."""
        from app.core.config import settings

        if _PERM_UPLOAD not in ctx.permissions:
            return Failure(
                error=AuthorizationError("permission_denied"),
                message=f"Permission '{_PERM_UPLOAD}' is required.",
            )

        if len(file_bytes) > settings.RAG_MAX_FILE_SIZE_BYTES:
            mb = settings.RAG_MAX_FILE_SIZE_BYTES // (1024 * 1024)
            return Failure(
                error=FileTooLargeError("file_too_large"),
                message=f"File exceeds the {mb} MB limit.",
            )

        # Extract text (raises UnsupportedFileTypeError / ValueError)
        try:
            text = extract_text(file_bytes, filename)
        except UnsupportedFileTypeError as exc:
            return Failure(error=exc, message=exc.message)
        except ValueError as exc:
            return Failure(error=exc, message=str(exc))

        # Chunk
        try:
            raw_chunks = chunk_text(
                text,
                chunk_size=settings.RAG_CHUNK_SIZE,
                overlap=settings.RAG_CHUNK_OVERLAP,
            )
        except ValueError as exc:
            return Failure(error=exc, message=str(exc))

        tenant_id: UUID = ctx.tenant_id

        # Detect content type from filename extension
        from pathlib import Path

        ext = Path(filename).suffix.lower().lstrip(".")
        content_type = f"text/{ext}" if ext else "text/plain"

        # Create document record (status = pending)
        doc = await self._docs.create(
            tenant_id=tenant_id,
            project_id=project_id,
            uploaded_by_user_id=ctx.current_user_id,
            filename=filename,
            content_type=content_type,
        )

        # Embed chunks and build DocumentChunk records
        chunk_records: list[DocumentChunk] = []
        try:
            embeddings = await self._embedder.embed_batch(raw_chunks)
        except EmbeddingError as exc:
            await self._docs.set_status(
                tenant_id=tenant_id,
                document_id=doc.id,
                status=DocumentStatus.FAILED,
            )
            return Failure(error=exc, message=exc.message)

        for idx, (chunk_content, embedding) in enumerate(
            zip(raw_chunks, embeddings, strict=True)
        ):
            label = make_citation_label(filename, idx)
            chunk_records.append(
                DocumentChunk(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    document_id=doc.id,
                    chunk_index=idx,
                    content=chunk_content,
                    content_hash=content_hash(chunk_content),
                    token_estimate=estimate_tokens(chunk_content),
                    embedding=embedding,
                    citation_label=label,
                )
            )

        await self._chunks.create_batch(chunk_records)

        # Mark indexed
        await self._docs.set_status(
            tenant_id=tenant_id,
            document_id=doc.id,
            status=DocumentStatus.INDEXED,
        )

        logger.info(
            "rag.upload document_id=%s chunks=%d filename_len=%d",
            doc.id,
            len(chunk_records),
            len(filename),  # filename length only, not content
        )

        return Success(
            DocumentUploadResponse(
                document_id=doc.id,
                filename=filename,
                status=DocumentStatus.INDEXED,
                chunk_count=len(chunk_records),
            )
        )

    # ── search ────────────────────────────────────────────────────────────────

    async def search(
        self,
        req: SearchRequest,
        ctx: SecurityContext,
    ) -> Result[SearchResponse]:
        """Embed the query and return the top-k most relevant chunks."""
        if _PERM_SEARCH not in ctx.permissions:
            return Failure(
                error=AuthorizationError("permission_denied"),
                message=f"Permission '{_PERM_SEARCH}' is required.",
            )

        tenant_id: UUID = ctx.tenant_id

        try:
            query_embedding = await self._embedder.embed(req.query)
        except EmbeddingError as exc:
            return Failure(error=exc, message=exc.message)

        from app.core.config import settings

        top_k = req.top_k or settings.RAG_TOP_K
        pairs = await self._chunks.search_similar(
            tenant_id=tenant_id,
            project_id=req.project_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        results: list[ChunkResult] = [
            ChunkResult(
                document_id=chunk.document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                citation_label=chunk.citation_label,
                excerpt=chunk.content[:500],  # safe excerpt, never full content
            )
            for chunk, filename in pairs
        ]

        logger.info(
            "rag.search tenant_id=%s project_id=%s query_chars=%d results=%d",
            tenant_id,
            req.project_id,
            len(req.query),  # length only
            len(results),
        )

        return Success(SearchResponse(results=results, query_chars=len(req.query)))

    # ── ask ───────────────────────────────────────────────────────────────────

    async def ask(
        self,
        req: AskRequest,
        ctx: SecurityContext,
    ) -> Result[AskResponse]:
        """Search for relevant chunks, generate an answer, return citations."""
        if _PERM_ASK not in ctx.permissions:
            return Failure(
                error=AuthorizationError("permission_denied"),
                message=f"Permission '{_PERM_ASK}' is required.",
            )

        tenant_id: UUID = ctx.tenant_id

        # Embed and retrieve context chunks.
        try:
            query_embedding = await self._embedder.embed(req.question)
        except EmbeddingError as exc:
            return Failure(error=exc, message=exc.message)

        from app.core.config import settings

        top_k = req.top_k or settings.RAG_TOP_K
        pairs = await self._chunks.search_similar(
            tenant_id=tenant_id,
            project_id=req.project_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        if not pairs:
            return Success(
                AskResponse(
                    answer="No relevant documents found for this question.",
                    citations=[],
                )
            )

        context_parts = [chunk.content for chunk, _ in pairs]
        context = "\n---\n".join(context_parts)
        prompt = _ASK_PROMPT_TEMPLATE.format(
            context=context,
            question=req.question,
        )

        logger.info(
            "rag.ask tenant_id=%s project_id=%s question_chars=%d context_chars=%d",
            tenant_id,
            req.project_id,
            len(req.question),  # never the content
            len(context),
        )

        try:
            gen_result = await self._answerer.generate(
                prompt,
                max_tokens=_ASK_MAX_TOKENS,
            )
        except AIProviderUnavailableError as exc:
            return Failure(error=exc, message=exc.message)

        citations: list[Citation] = build_citations(
            [(chunk, filename) for chunk, filename in pairs]
        )

        # Track usage (non-fatal).
        try:
            await self._usage.increment(
                tenant_id=tenant_id,
                billing_period=_billing_period(),
                project_id=req.project_id,
                ai_call_count=1,
                token_usage=(
                    gen_result.input_tokens_estimate + gen_result.output_tokens_estimate
                ),
            )
        except Exception:  # noqa: BLE001
            logger.exception("rag.usage_persist_failed tenant_id=%s", tenant_id)

        return Success(
            AskResponse(
                answer=gen_result.output,
                citations=citations,
                provider=gen_result.provider,
                model=gen_result.model,
            )
        )

    # ── list documents ────────────────────────────────────────────────────────

    async def list_documents(
        self,
        project_id: UUID,
        ctx: SecurityContext,
    ) -> Result[list[DocumentListItem]]:
        """List all indexed documents for a tenant+project pair."""
        if _PERM_SEARCH not in ctx.permissions:
            return Failure(
                error=AuthorizationError("permission_denied"),
                message=f"Permission '{_PERM_SEARCH}' is required.",
            )

        tenant_id: UUID = ctx.tenant_id
        docs = await self._docs.list_by_project(
            tenant_id=tenant_id, project_id=project_id
        )

        items = [
            DocumentListItem(
                document_id=doc.id,
                filename=doc.filename,
                content_type=doc.content_type,
                status=doc.status,
                created_at=doc.created_at,
            )
            for doc in docs
        ]
        return Success(items)
