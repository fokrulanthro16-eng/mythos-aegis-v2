"""Vision Intelligence API routes.

Endpoints:
  POST /v1/vision/analyze  — analyze an image with the vision model
  POST /v1/vision/ocr      — OCR-extract text from an image
  POST /v1/vision/extract  — extract text from a PDF document

All endpoints require a Bearer JWT.
Permissions:
  vision.analyze — POST /v1/vision/analyze, POST /v1/vision/ocr
  vision.extract — POST /v1/vision/extract
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_security_context
from app.core.exceptions import (
    ImageTooLargeError,
    UnsupportedFileTypeError,
    VisionProviderUnavailableError,
)
from app.core.security_context import SecurityContext
from app.db.session import get_session
from app.vision.schemas import OCRResponse, PDFExtractResponse, VisionAnalyzeResponse
from app.vision.service import VisionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/vision", tags=["vision"])

_SecurityCtx = Annotated[SecurityContext, Depends(get_security_context)]
_DbSession = Annotated[AsyncSession, Depends(get_session)]

_PERM_ANALYZE = "vision.analyze"
_PERM_EXTRACT = "vision.extract"


def _require(ctx: SecurityContext, perm: str) -> None:
    if perm not in ctx.permissions:
        raise HTTPException(status_code=403, detail=f"Permission '{perm}' required")


def _parse_project_id(project_id: str) -> UUID:
    try:
        return UUID(project_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="project_id must be a valid UUID"
        ) from exc


# ── POST /v1/vision/analyze ───────────────────────────────────────────────────


@router.post("/analyze", response_model=VisionAnalyzeResponse, status_code=200)
async def analyze_image(
    file: UploadFile,
    ctx: _SecurityCtx,
    session: _DbSession,
    project_id: str = Form(...),
    prompt: str = Form(default=""),
    index_into_rag: bool = Form(default=False),
) -> VisionAnalyzeResponse:
    """Analyze an image with the local vision model.

    Supported formats: JPEG, PNG, WebP, GIF.
    Permission: vision.analyze
    """
    _require(ctx, _PERM_ANALYZE)
    pid = _parse_project_id(project_id)

    file_bytes = await file.read()
    filename = file.filename or "upload.jpg"

    svc = VisionService(session)
    try:
        return await svc.analyze_image(
            file_bytes=file_bytes,
            filename=filename,
            ctx=ctx,
            prompt=prompt.strip() or None,
            project_id=pid,
            index_into_rag=index_into_rag,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=415, detail=exc.message) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(status_code=413, detail=exc.message) from exc
    except VisionProviderUnavailableError as exc:
        logger.warning("vision.route.analyze_unavailable: %s", exc.message)
        raise HTTPException(status_code=503, detail=exc.message) from exc


# ── POST /v1/vision/ocr ───────────────────────────────────────────────────────


@router.post("/ocr", response_model=OCRResponse, status_code=200)
async def ocr_image(
    file: UploadFile,
    ctx: _SecurityCtx,
    session: _DbSession,
    project_id: str = Form(default=""),
    index_into_rag: bool = Form(default=False),
) -> OCRResponse:
    """Extract text from an image using OCR via the vision model.

    Supported formats: JPEG, PNG, WebP, GIF.
    Permission: vision.analyze
    """
    _require(ctx, _PERM_ANALYZE)

    pid: UUID | None = None
    if project_id.strip():
        pid = _parse_project_id(project_id.strip())

    file_bytes = await file.read()
    filename = file.filename or "upload.jpg"

    svc = VisionService(session)
    try:
        return await svc.ocr_image(
            file_bytes=file_bytes,
            filename=filename,
            ctx=ctx,
            project_id=pid,
            index_into_rag=index_into_rag and pid is not None,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=415, detail=exc.message) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(status_code=413, detail=exc.message) from exc
    except VisionProviderUnavailableError as exc:
        logger.warning("vision.route.ocr_unavailable: %s", exc.message)
        raise HTTPException(status_code=503, detail=exc.message) from exc


# ── POST /v1/vision/extract ───────────────────────────────────────────────────


@router.post("/extract", response_model=PDFExtractResponse, status_code=200)
async def extract_document(
    file: UploadFile,
    ctx: _SecurityCtx,
    session: _DbSession,
    project_id: str = Form(...),
    index_into_rag: bool = Form(default=True),
) -> PDFExtractResponse:
    """Extract text from a PDF document using pypdf.

    Permission: vision.extract
    """
    _require(ctx, _PERM_EXTRACT)
    pid = _parse_project_id(project_id)

    file_bytes = await file.read()
    filename = file.filename or "document.pdf"

    svc = VisionService(session)
    try:
        return await svc.extract_pdf(
            pdf_bytes=file_bytes,
            filename=filename,
            ctx=ctx,
            project_id=pid,
            index_into_rag=index_into_rag,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=415, detail=exc.message) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(status_code=413, detail=exc.message) from exc
