"""RAG API routes.

All endpoints require a Bearer JWT. Permissions:
  rag.upload — POST /v1/rag/upload
  rag.search — POST /v1/rag/search, GET /v1/rag/documents
  rag.ask    — POST /v1/rag/ask
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_security_context
from app.core.exceptions import (
    AIProviderUnavailableError,
    AuthorizationError,
    EmbeddingError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.core.result import Failure, Success
from app.core.security_context import SecurityContext
from app.db.session import get_session
from app.rag.schemas import (
    AskRequest,
    AskResponse,
    DocumentListItem,
    DocumentUploadResponse,
    SearchRequest,
    SearchResponse,
)
from app.rag.service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/rag", tags=["rag"])

_SecurityCtx = Annotated[SecurityContext, Depends(get_security_context)]
_DbSession = Annotated[AsyncSession, Depends(get_session)]


def _map_failure(result: Failure) -> None:
    """Raise an appropriate HTTPException for a typed Failure."""
    err = result.error
    msg = result.message or str(err)
    if isinstance(err, AuthorizationError):
        raise HTTPException(status_code=403, detail=msg)
    if isinstance(err, FileTooLargeError):
        raise HTTPException(status_code=413, detail=msg)
    if isinstance(err, UnsupportedFileTypeError):
        raise HTTPException(status_code=400, detail=msg)
    if isinstance(err, (AIProviderUnavailableError, EmbeddingError)):
        raise HTTPException(status_code=503, detail=msg)
    raise HTTPException(status_code=500, detail=msg)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    project_id: Annotated[UUID, Form()],
    ctx: _SecurityCtx,
    session: _DbSession,
) -> DocumentUploadResponse:
    """Upload and index a document.

    Supported file types: .txt, .md, .json, .csv, .pdf
    Max size: 10 MB
    Permission: rag.upload
    """
    file_bytes = await file.read()
    filename = file.filename or "upload"

    svc = RAGService(session)
    result = await svc.upload_document(
        file_bytes=file_bytes,
        filename=filename,
        project_id=project_id,
        ctx=ctx,
    )

    if isinstance(result, Success):
        return result.value
    _map_failure(result)
    raise HTTPException(status_code=500, detail="Unexpected error")  # unreachable


@router.post("/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> SearchResponse:
    """Semantic search over tenant-scoped documents.

    Permission: rag.search
    """
    svc = RAGService(session)
    result = await svc.search(req, ctx)

    if isinstance(result, Success):
        return result.value
    _map_failure(result)
    raise HTTPException(status_code=500, detail="Unexpected error")  # unreachable


@router.post("/ask", response_model=AskResponse)
async def ask(
    req: AskRequest,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> AskResponse:
    """Ask a question and get an answer grounded in tenant documents.

    Permission: rag.ask
    Returns the answer plus citations for every source chunk used.
    """
    svc = RAGService(session)
    result = await svc.ask(req, ctx)

    if isinstance(result, Success):
        return result.value
    _map_failure(result)
    raise HTTPException(status_code=500, detail="Unexpected error")  # unreachable


@router.get("/documents", response_model=list[DocumentListItem])
async def list_documents(
    project_id: UUID,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> list[DocumentListItem]:
    """List all documents for the authenticated tenant and project.

    Permission: rag.search
    """
    svc = RAGService(session)
    result = await svc.list_documents(project_id, ctx)

    if isinstance(result, Success):
        return result.value
    _map_failure(result)
    raise HTTPException(status_code=500, detail="Unexpected error")  # unreachable
