"""HTTP-layer tests for the vision router.

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

from app.core.security_context import SecurityContext
from app.vision.schemas import OCRResponse, PDFExtractResponse, VisionAnalyzeResponse

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_ctx(permissions: frozenset[str] | None = None) -> SecurityContext:
    if permissions is None:
        permissions = frozenset({"vision.analyze", "vision.extract"})
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=permissions,
    )


def _make_client(ctx: SecurityContext) -> Generator[TestClient, None, None]:
    from app.auth.dependencies import get_security_context
    from app.db.session import get_session
    from app.main import app

    app.dependency_overrides[get_security_context] = lambda: ctx
    app.dependency_overrides[get_session] = lambda: AsyncMock()

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
def client() -> Generator[TestClient, None, None]:
    yield from _make_client(_make_ctx())


@pytest.fixture
def client_no_perms() -> Generator[TestClient, None, None]:
    yield from _make_client(_make_ctx(frozenset()))


@pytest.fixture
def client_analyze_only() -> Generator[TestClient, None, None]:
    yield from _make_client(_make_ctx(frozenset({"vision.analyze"})))


@pytest.fixture
def client_extract_only() -> Generator[TestClient, None, None]:
    yield from _make_client(_make_ctx(frozenset({"vision.extract"})))


def _analyze_response() -> VisionAnalyzeResponse:
    return VisionAnalyzeResponse(
        analysis="A chart with revenue data.",
        model="qwen2.5-vl:7b",
        filename="chart.png",
        file_type="image/png",
    )


def _ocr_response() -> OCRResponse:
    return OCRResponse(
        filename="scan.jpg",
        text="Contract terms follow.",
        model="qwen2.5-vl:7b",
        char_count=22,
    )


def _pdf_response() -> PDFExtractResponse:
    return PDFExtractResponse(
        filename="report.pdf",
        page_count=2,
        text_pages=["Page one content.", "Page two content."],
        total_chars=35,
    )


# ── POST /v1/vision/analyze ───────────────────────────────────────────────────


class TestAnalyzeEndpoint:
    def test_analyze_returns_200(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.analyze_image = AsyncMock(return_value=_analyze_response())

        with patch("app.vision.routes.VisionService", return_value=svc):
            resp = client.post(
                "/v1/vision/analyze",
                data={"project_id": str(uuid4()), "prompt": "Describe it."},
                files={"file": ("chart.png", io.BytesIO(b"\x89PNG"), "image/png")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["analysis"] == "A chart with revenue data."
        assert body["model"] == "qwen2.5-vl:7b"
        assert body["filename"] == "chart.png"

    def test_analyze_returns_403_without_permission(
        self, client_no_perms: TestClient
    ) -> None:
        resp = client_no_perms.post(
            "/v1/vision/analyze",
            data={"project_id": str(uuid4())},
            files={"file": ("img.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
        )
        assert resp.status_code == 403

    def test_analyze_returns_415_for_unsupported_type(self, client: TestClient) -> None:
        from app.core.exceptions import UnsupportedFileTypeError

        svc = MagicMock()
        svc.analyze_image = AsyncMock(
            side_effect=UnsupportedFileTypeError("Unsupported file type '.bmp'")
        )

        with patch("app.vision.routes.VisionService", return_value=svc):
            resp = client.post(
                "/v1/vision/analyze",
                data={"project_id": str(uuid4())},
                files={"file": ("img.bmp", io.BytesIO(b"BM"), "image/bmp")},
            )

        assert resp.status_code == 415

    def test_analyze_returns_413_for_large_file(self, client: TestClient) -> None:
        from app.core.exceptions import ImageTooLargeError

        svc = MagicMock()
        svc.analyze_image = AsyncMock(
            side_effect=ImageTooLargeError("Image exceeds maximum size")
        )

        with patch("app.vision.routes.VisionService", return_value=svc):
            resp = client.post(
                "/v1/vision/analyze",
                data={"project_id": str(uuid4())},
                files={"file": ("big.png", io.BytesIO(b"x" * 100), "image/png")},
            )

        assert resp.status_code == 413

    def test_analyze_returns_503_when_provider_unavailable(
        self, client: TestClient
    ) -> None:
        from app.core.exceptions import VisionProviderUnavailableError

        svc = MagicMock()
        svc.analyze_image = AsyncMock(
            side_effect=VisionProviderUnavailableError("Ollama unreachable")
        )

        with patch("app.vision.routes.VisionService", return_value=svc):
            resp = client.post(
                "/v1/vision/analyze",
                data={"project_id": str(uuid4())},
                files={"file": ("img.jpg", io.BytesIO(b"\xff\xd8"), "image/jpeg")},
            )

        assert resp.status_code == 503

    def test_analyze_returns_422_for_invalid_project_id(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/v1/vision/analyze",
            data={"project_id": "not-a-uuid"},
            files={"file": ("img.png", io.BytesIO(b"\x89PNG"), "image/png")},
        )
        assert resp.status_code == 422


# ── POST /v1/vision/ocr ───────────────────────────────────────────────────────


class TestOCREndpoint:
    def test_ocr_returns_200(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.ocr_image = AsyncMock(return_value=_ocr_response())

        with patch("app.vision.routes.VisionService", return_value=svc):
            resp = client.post(
                "/v1/vision/ocr",
                data={"project_id": ""},
                files={"file": ("scan.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "Contract terms follow."
        assert body["char_count"] == 22

    def test_ocr_returns_403_without_permission(
        self, client_no_perms: TestClient
    ) -> None:
        resp = client_no_perms.post(
            "/v1/vision/ocr",
            data={"project_id": ""},
            files={"file": ("scan.jpg", io.BytesIO(b"\xff\xd8"), "image/jpeg")},
        )
        assert resp.status_code == 403

    def test_ocr_returns_415_for_unsupported_type(self, client: TestClient) -> None:
        from app.core.exceptions import UnsupportedFileTypeError

        svc = MagicMock()
        svc.ocr_image = AsyncMock(
            side_effect=UnsupportedFileTypeError("Unsupported file type '.txt'")
        )

        with patch("app.vision.routes.VisionService", return_value=svc):
            resp = client.post(
                "/v1/vision/ocr",
                data={"project_id": ""},
                files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")},
            )

        assert resp.status_code == 415

    def test_ocr_with_valid_project_id(self, client: TestClient) -> None:
        pid = str(uuid4())
        svc = MagicMock()
        svc.ocr_image = AsyncMock(return_value=_ocr_response())

        with patch("app.vision.routes.VisionService", return_value=svc):
            resp = client.post(
                "/v1/vision/ocr",
                data={"project_id": pid},
                files={"file": ("scan.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
            )

        assert resp.status_code == 200
        svc.ocr_image.assert_awaited_once()


# ── POST /v1/vision/extract ───────────────────────────────────────────────────


class TestExtractEndpoint:
    def test_extract_returns_200(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.extract_pdf = AsyncMock(return_value=_pdf_response())

        with patch("app.vision.routes.VisionService", return_value=svc):
            resp = client.post(
                "/v1/vision/extract",
                data={"project_id": str(uuid4())},
                files={
                    "file": ("report.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "report.pdf"
        assert body["page_count"] == 2
        assert body["total_chars"] == 35

    def test_extract_returns_403_without_extract_permission(
        self, client_analyze_only: TestClient
    ) -> None:
        resp = client_analyze_only.post(
            "/v1/vision/extract",
            data={"project_id": str(uuid4())},
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
        assert resp.status_code == 403

    def test_extract_returns_415_for_image(self, client: TestClient) -> None:
        from app.core.exceptions import UnsupportedFileTypeError

        svc = MagicMock()
        svc.extract_pdf = AsyncMock(
            side_effect=UnsupportedFileTypeError(
                "extract endpoint only accepts PDF files"
            )
        )

        with patch("app.vision.routes.VisionService", return_value=svc):
            resp = client.post(
                "/v1/vision/extract",
                data={"project_id": str(uuid4())},
                files={"file": ("image.png", io.BytesIO(b"\x89PNG"), "image/png")},
            )

        assert resp.status_code == 415

    def test_extract_returns_422_for_invalid_project_id(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/v1/vision/extract",
            data={"project_id": "bad-id"},
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
        assert resp.status_code == 422

    def test_extract_analyze_perm_insufficient(
        self, client_analyze_only: TestClient
    ) -> None:
        resp = client_analyze_only.post(
            "/v1/vision/extract",
            data={"project_id": str(uuid4())},
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
        assert resp.status_code == 403
