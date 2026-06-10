"""Vision Intelligence Service.

Orchestrates image analysis, PDF text extraction, and optional RAG indexing.

Security invariants:
- Image/document bytes are NEVER written to any log.
- Prompt content is NEVER logged — only character counts.
- tenant_id is ALWAYS sourced from the validated SecurityContext.
- Every operation is recorded in the vision_events audit table.
"""

from __future__ import annotations

import json as _json
import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security_context import SecurityContext
from app.db.models.vision_event import VisionEvent
from app.vision.processor import extract_pdf_text, is_pdf_file, validate_file
from app.vision.providers.base import BaseVisionProvider
from app.vision.providers.factory import get_vision_provider
from app.vision.schemas import OCRResponse, PDFExtractResponse, VisionAnalyzeResponse

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = (
    "Describe this image in detail. "
    "Extract any visible text exactly as written. "
    "Note tables, charts, diagrams, and structured data."
)

_OCR_PROMPT = (
    "Perform OCR on this image. "
    "Extract all text exactly as it appears, preserving layout and structure. "
    "Return only the extracted text, nothing else."
)

_SCREENSHOT_PROMPT = (
    "Analyze this screenshot. "
    "Describe the UI elements, content, and any visible data. "
    "Extract all text and structured information."
)


def _extract_summary(content: str, provider_name: str) -> str:
    """Return a display-friendly summary from provider output.

    Gemini returns a JSON object; extract its 'summary' key.
    All other providers return freetext which is used as-is.
    """
    if provider_name == "gemini":
        try:
            data = _json.loads(content)
            return str(data.get("summary", content))
        except (_json.JSONDecodeError, AttributeError, TypeError):
            return content
    return content


class VisionService:
    """Orchestrate vision analysis with tenant isolation and audit logging."""

    def __init__(
        self,
        db_session: AsyncSession,
        provider: BaseVisionProvider | None = None,
    ) -> None:
        self._db = db_session
        self._provider = provider or get_vision_provider()

    # ── Image analysis ────────────────────────────────────────────────────────

    async def analyze_image(
        self,
        file_bytes: bytes,
        filename: str,
        ctx: SecurityContext,
        *,
        prompt: str | None = None,
        project_id: UUID | None = None,
        index_into_rag: bool = False,
    ) -> VisionAnalyzeResponse:
        """Analyze an image with the vision model."""
        mime_type = validate_file(filename, file_bytes)
        effective_prompt = prompt or _DEFAULT_PROMPT

        result = await self._provider.analyze(
            file_bytes, effective_prompt, mime_type=mime_type
        )

        provider_name = self._provider.provider_name
        summary = _extract_summary(result.content, provider_name)

        index_status: str | None = None
        document_id: UUID | None = None

        if index_into_rag and project_id:
            document_id, index_status = await self._index_text(
                text=result.content,
                source_filename=f"{filename}.vision.txt",
                project_id=project_id,
                ctx=ctx,
            )

        await self._log_event(
            ctx=ctx,
            filename=filename,
            file_type=mime_type,
            file_size=len(file_bytes),
            model_used=result.model,
            prompt_chars=len(effective_prompt),
            output_chars=len(result.content),
            project_id=project_id,
            indexed=index_status == "indexed",
        )

        logger.info(
            "vision.analyze provider=%s tenant=%s file_type=%s output_chars=%d",
            provider_name,
            ctx.tenant_id,
            mime_type,
            len(result.content),
        )

        return VisionAnalyzeResponse(
            analysis=result.content,
            summary=summary,
            provider=provider_name,
            model=result.model,
            filename=filename,
            file_type=mime_type,
            index_status=index_status,
            document_id=document_id,
        )

    # ── OCR ───────────────────────────────────────────────────────────────────

    async def ocr_image(
        self,
        file_bytes: bytes,
        filename: str,
        ctx: SecurityContext,
        *,
        project_id: UUID | None = None,
        index_into_rag: bool = False,
    ) -> OCRResponse:
        """Run OCR on an image and return extracted text."""
        mime_type = validate_file(filename, file_bytes)

        result = await self._provider.analyze(
            file_bytes, _OCR_PROMPT, mime_type=mime_type
        )

        if index_into_rag and project_id:
            await self._index_text(
                text=result.content,
                source_filename=f"{filename}.ocr.txt",
                project_id=project_id,
                ctx=ctx,
            )

        await self._log_event(
            ctx=ctx,
            filename=filename,
            file_type=mime_type,
            file_size=len(file_bytes),
            model_used=result.model,
            prompt_chars=len(_OCR_PROMPT),
            output_chars=len(result.content),
            project_id=project_id,
            indexed=index_into_rag and project_id is not None,
        )

        return OCRResponse(
            filename=filename,
            text=result.content,
            model=result.model,
            char_count=len(result.content),
        )

    # ── PDF extraction ────────────────────────────────────────────────────────

    async def extract_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        ctx: SecurityContext,
        *,
        project_id: UUID | None = None,
        index_into_rag: bool = False,
    ) -> PDFExtractResponse:
        """Extract text from a PDF using pypdf."""
        validate_file(filename, pdf_bytes)

        if not is_pdf_file(filename):
            from app.core.exceptions import UnsupportedFileTypeError

            raise UnsupportedFileTypeError("extract endpoint only accepts PDF files")

        pages = extract_pdf_text(pdf_bytes)
        total_chars = sum(len(p) for p in pages)

        index_status: str | None = None
        document_id: UUID | None = None

        if index_into_rag and project_id and total_chars > 0:
            combined = "\n\n".join(
                f"[Page {i + 1}]\n{p}" for i, p in enumerate(pages) if p.strip()
            )
            document_id, index_status = await self._index_text(
                text=combined,
                source_filename=f"{filename}.txt",
                project_id=project_id,
                ctx=ctx,
            )

        await self._log_event(
            ctx=ctx,
            filename=filename,
            file_type="application/pdf",
            file_size=len(pdf_bytes),
            model_used="pypdf",
            prompt_chars=0,
            output_chars=total_chars,
            project_id=project_id,
            indexed=index_status == "indexed",
        )

        logger.info(
            "vision.pdf.extract tenant=%s pages=%d total_chars=%d",
            ctx.tenant_id,
            len(pages),
            total_chars,
        )

        return PDFExtractResponse(
            filename=filename,
            page_count=len(pages),
            text_pages=pages,
            total_chars=total_chars,
            index_status=index_status,
            document_id=document_id,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _index_text(
        self,
        text: str,
        source_filename: str,
        project_id: UUID,
        ctx: SecurityContext,
    ) -> tuple[UUID | None, str]:
        """Index extracted text into the RAG store; return (doc_id, status)."""
        try:
            from app.core.result import Success
            from app.rag.service import RAGService

            rag = RAGService(self._db)
            outcome = await rag.upload_document(
                file_bytes=text.encode("utf-8"),
                filename=source_filename,
                project_id=project_id,
                ctx=ctx,
            )
            if isinstance(outcome, Success):
                return outcome.value.document_id, "indexed"
            logger.warning("vision.rag_index_failed reason=%s", outcome.message)
            return None, "index_failed"
        except Exception:
            logger.warning("vision.rag_index_error filename=%s", source_filename)
            return None, "index_failed"

    async def _log_event(
        self,
        *,
        ctx: SecurityContext,
        filename: str,
        file_type: str,
        file_size: int,
        model_used: str,
        prompt_chars: int,
        output_chars: int,
        project_id: UUID | None,
        indexed: bool,
    ) -> UUID:
        event_id = uuid4()
        event = VisionEvent(
            id=event_id,
            tenant_id=ctx.tenant_id,
            user_id=ctx.current_user_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=file_size,
            model_used=model_used,
            prompt_chars=prompt_chars,
            output_chars=output_chars,
            project_id=project_id,
            indexed_into_rag=indexed,
        )
        self._db.add(event)
        await self._db.flush()
        return event_id
