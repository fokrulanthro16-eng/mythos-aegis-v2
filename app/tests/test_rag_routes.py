"""HTTP-layer tests for the RAG router.

Uses FastAPI's dependency-override mechanism to bypass JWTAuthMiddleware
and inject mock service results.  No Ollama or Postgres required.
"""

from __future__ import annotations

import io
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.result import Failure, Success
from app.core.security_context import SecurityContext
from app.rag.schemas import (
    AskResponse,
    ChunkResult,
    Citation,
    DocumentListItem,
    DocumentUploadResponse,
    SearchResponse,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_ctx(permissions: frozenset[str] | None = None) -> SecurityContext:
    if permissions is None:
        permissions = frozenset({"rag.upload", "rag.search", "rag.ask"})
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=permissions,
    )


def _make_client(ctx: SecurityContext) -> Generator[TestClient, None, None]:
    """Fixture factory: overrides security/session deps and bypasses JWT middleware."""
    from app.auth.dependencies import get_security_context
    from app.db.session import get_session
    from app.main import app

    app.dependency_overrides[get_security_context] = lambda: ctx
    app.dependency_overrides[get_session] = lambda: AsyncMock()

    # JWTAuthMiddleware runs before dependency resolution; patch its internals so
    # any Bearer token is accepted and the correct context is injected.
    with (
        patch("app.auth.middleware.validate_token", return_value={}),
        patch("app.auth.middleware.build_security_context", return_value=ctx),
    ):
        yield TestClient(
            app,
            raise_server_exceptions=False,
            headers={"Authorization": "Bearer test-token"},
        )

    app.dependency_overrides.clear()


@pytest.fixture
def client_full() -> Generator[TestClient, None, None]:
    """TestClient with full RAG permissions."""
    yield from _make_client(_make_ctx())


@pytest.fixture
def client_no_perms() -> Generator[TestClient, None, None]:
    """TestClient with no permissions."""
    yield from _make_client(_make_ctx(frozenset()))


# ── POST /v1/rag/upload ───────────────────────────────────────────────────────


def test_upload_returns_200_on_success(client_full: TestClient) -> None:
    doc_id = uuid4()
    upload_response = DocumentUploadResponse(
        document_id=doc_id,
        filename="policy.txt",
        status="indexed",
        chunk_count=5,
    )
    mock_svc = MagicMock()
    mock_svc.upload_document = AsyncMock(return_value=Success(upload_response))

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_full.post(
            "/v1/rag/upload",
            data={"project_id": str(uuid4())},
            files={"file": ("policy.txt", io.BytesIO(b"content"), "text/plain")},
        )

    assert resp.status_code == 200
    assert resp.json()["filename"] == "policy.txt"
    assert resp.json()["chunk_count"] == 5


def test_upload_returns_403_without_permission(client_no_perms: TestClient) -> None:
    from app.core.exceptions import AuthorizationError

    mock_svc = MagicMock()
    mock_svc.upload_document = AsyncMock(
        return_value=Failure(
            error=AuthorizationError("permission_denied"),
            message="Permission 'rag.upload' is required.",
        )
    )

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_no_perms.post(
            "/v1/rag/upload",
            data={"project_id": str(uuid4())},
            files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")},
        )

    assert resp.status_code == 403


def test_upload_returns_400_for_unsupported_type(client_full: TestClient) -> None:
    from app.core.exceptions import UnsupportedFileTypeError

    mock_svc = MagicMock()
    mock_svc.upload_document = AsyncMock(
        return_value=Failure(
            error=UnsupportedFileTypeError("Unsupported file type '.pdf'"),
            message="Unsupported file type '.pdf'.",
        )
    )

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_full.post(
            "/v1/rag/upload",
            data={"project_id": str(uuid4())},
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )

    assert resp.status_code == 400


# ── POST /v1/rag/search ───────────────────────────────────────────────────────


def test_search_returns_200(client_full: TestClient) -> None:
    search_response = SearchResponse(results=[], query_chars=15)
    mock_svc = MagicMock()
    mock_svc.search = AsyncMock(return_value=Success(search_response))

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_full.post(
            "/v1/rag/search",
            json={"project_id": str(uuid4()), "query": "vacation policy"},
        )

    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_search_returns_403_without_permission(client_no_perms: TestClient) -> None:
    from app.core.exceptions import AuthorizationError

    mock_svc = MagicMock()
    mock_svc.search = AsyncMock(
        return_value=Failure(
            error=AuthorizationError("permission_denied"),
            message="Permission 'rag.search' is required.",
        )
    )

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_no_perms.post(
            "/v1/rag/search",
            json={"project_id": str(uuid4()), "query": "anything"},
        )

    assert resp.status_code == 403


def test_search_returns_503_when_embedding_fails(client_full: TestClient) -> None:
    from app.core.exceptions import EmbeddingError

    mock_svc = MagicMock()
    mock_svc.search = AsyncMock(
        return_value=Failure(
            error=EmbeddingError("Ollama down"),
            message="Ollama not reachable.",
        )
    )

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_full.post(
            "/v1/rag/search",
            json={"project_id": str(uuid4()), "query": "test"},
        )

    assert resp.status_code == 503


# ── POST /v1/rag/ask ──────────────────────────────────────────────────────────


def test_ask_returns_200(client_full: TestClient) -> None:
    ask_response = AskResponse(
        answer="The answer is 42.",
        citations=[
            Citation(
                document_id=uuid4(),
                filename="doc.txt",
                chunk_index=0,
                citation_label="doc#chunk-0",
            )
        ],
    )
    mock_svc = MagicMock()
    mock_svc.ask = AsyncMock(return_value=Success(ask_response))

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_full.post(
            "/v1/rag/ask",
            json={"project_id": str(uuid4()), "question": "What is the answer?"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "The answer is 42."
    assert len(body["citations"]) == 1


def test_ask_returns_503_when_provider_unavailable(client_full: TestClient) -> None:
    from app.core.exceptions import AIProviderUnavailableError

    mock_svc = MagicMock()
    mock_svc.ask = AsyncMock(
        return_value=Failure(
            error=AIProviderUnavailableError("Ollama down"),
            message="Ollama not reachable",
        )
    )

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_full.post(
            "/v1/rag/ask",
            json={"project_id": str(uuid4()), "question": "?"},
        )

    assert resp.status_code == 503


def test_ask_returns_403_without_permission(client_no_perms: TestClient) -> None:
    from app.core.exceptions import AuthorizationError

    mock_svc = MagicMock()
    mock_svc.ask = AsyncMock(
        return_value=Failure(
            error=AuthorizationError("permission_denied"),
            message="Permission 'rag.ask' is required.",
        )
    )

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_no_perms.post(
            "/v1/rag/ask",
            json={"project_id": str(uuid4()), "question": "?"},
        )

    assert resp.status_code == 403


# ── GET /v1/rag/documents ─────────────────────────────────────────────────────


def test_list_documents_returns_200(client_full: TestClient) -> None:
    from datetime import UTC, datetime

    docs = [
        DocumentListItem(
            document_id=uuid4(),
            filename="policy.txt",
            content_type="text/plain",
            status="indexed",
            created_at=datetime.now(UTC),
        )
    ]
    mock_svc = MagicMock()
    mock_svc.list_documents = AsyncMock(return_value=Success(docs))

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_full.get(
            "/v1/rag/documents",
            params={"project_id": str(uuid4())},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["filename"] == "policy.txt"


def test_list_documents_returns_403_without_permission(
    client_no_perms: TestClient,
) -> None:
    from app.core.exceptions import AuthorizationError

    mock_svc = MagicMock()
    mock_svc.list_documents = AsyncMock(
        return_value=Failure(
            error=AuthorizationError("permission_denied"),
            message="Permission 'rag.search' is required.",
        )
    )

    with patch("app.rag.routes.RAGService", return_value=mock_svc):
        resp = client_no_perms.get(
            "/v1/rag/documents",
            params={"project_id": str(uuid4())},
        )

    assert resp.status_code == 403


# ── Response schema: no raw embeddings ────────────────────────────────────────


def test_search_response_has_no_embedding_field() -> None:
    result = ChunkResult(
        document_id=uuid4(),
        filename="doc.txt",
        chunk_index=0,
        citation_label="doc#chunk-0",
        excerpt="Some content.",
    )
    assert not hasattr(result, "embedding")
    data = result.model_dump()
    assert "embedding" not in data


def test_ask_response_has_citations() -> None:
    resp = AskResponse(
        answer="Answer text.",
        citations=[
            Citation(
                document_id=uuid4(),
                filename="policy.md",
                chunk_index=2,
                citation_label="policy#chunk-2",
            )
        ],
    )
    assert resp.citations[0].citation_label == "policy#chunk-2"
    assert resp.citations[0].filename == "policy.md"
