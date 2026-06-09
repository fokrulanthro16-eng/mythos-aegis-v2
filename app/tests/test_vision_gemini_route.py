"""HTTP-layer tests for POST /vision/analyze (Gemini Cloud Vision).

Uses FastAPI dependency_overrides to inject a fake SecurityContext and mocks
GeminiVisionProvider so no real Gemini API key is required.
"""

from __future__ import annotations

import io
import json
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import VisionProviderUnavailableError
from app.core.security_context import SecurityContext
from app.vision.providers.base import VisionAnalysisResult

_ANALYZE_URL = "/vision/analyze"

_VALID_CONTENT = json.dumps(
    {
        "summary": "A red sports car parked on a street.",
        "detected_objects": ["car", "street", "pavement"],
        "observations": ["The car is red.", "Daylight conditions."],
    }
)


def _make_ctx(permissions: frozenset[str] | None = None) -> SecurityContext:
    if permissions is None:
        permissions = frozenset({"vision.analyze"})
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=permissions,
    )


def _make_client(ctx: SecurityContext) -> Generator[TestClient, None, None]:
    from app.auth.dependencies import get_security_context
    from app.main import app

    app.dependency_overrides[get_security_context] = lambda: ctx

    with (
        patch("app.auth.middleware.validate_token", return_value={}),
        patch("app.auth.middleware.build_security_context", return_value=ctx),
    ):
        yield TestClient(
            app,
            raise_server_exceptions=False,
            headers={"Authorization": "Bearer test-token"},
        )

    app.dependency_overrides.pop(get_security_context, None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    yield from _make_client(_make_ctx())


@pytest.fixture
def client_no_perms() -> Generator[TestClient, None, None]:
    yield from _make_client(_make_ctx(frozenset()))


def _fake_image() -> tuple[str, io.BytesIO, str]:
    return ("file", io.BytesIO(b"fake-jpeg-bytes"), "image/jpeg")


def _mock_provider(content: str) -> MagicMock:
    mock_instance = AsyncMock()
    mock_instance.analyze.return_value = VisionAnalysisResult(
        content=content, model="gemini-test-flash", input_tokens=50, output_tokens=20
    )
    mock_cls = MagicMock(return_value=mock_instance)
    return mock_cls


# ── Authentication ────────────────────────────────────────────────────────────


def test_analyze_requires_jwt(client: TestClient) -> None:
    from app.main import app

    app.dependency_overrides.clear()
    bare = TestClient(app, raise_server_exceptions=False)
    resp = bare.post(_ANALYZE_URL, files={"file": _fake_image()})
    assert resp.status_code == 401


# ── Authorization ─────────────────────────────────────────────────────────────


def test_analyze_returns_403_without_permission(
    client_no_perms: TestClient,
) -> None:
    with patch(
        "app.vision.routes.GeminiVisionProvider",
        _mock_provider(_VALID_CONTENT),
    ):
        resp = client_no_perms.post(_ANALYZE_URL, files={"file": _fake_image()})
    assert resp.status_code == 403


# ── Success ───────────────────────────────────────────────────────────────────


def test_analyze_returns_200(client: TestClient) -> None:
    with patch(
        "app.vision.routes.GeminiVisionProvider",
        _mock_provider(_VALID_CONTENT),
    ):
        resp = client.post(_ANALYZE_URL, files={"file": _fake_image()})
    assert resp.status_code == 200


def test_analyze_response_has_summary(client: TestClient) -> None:
    with patch(
        "app.vision.routes.GeminiVisionProvider",
        _mock_provider(_VALID_CONTENT),
    ):
        resp = client.post(_ANALYZE_URL, files={"file": _fake_image()})
    assert resp.json()["summary"] == "A red sports car parked on a street."


def test_analyze_response_has_detected_objects(client: TestClient) -> None:
    with patch(
        "app.vision.routes.GeminiVisionProvider",
        _mock_provider(_VALID_CONTENT),
    ):
        resp = client.post(_ANALYZE_URL, files={"file": _fake_image()})
    assert resp.json()["detected_objects"] == ["car", "street", "pavement"]


def test_analyze_response_has_observations(client: TestClient) -> None:
    with patch(
        "app.vision.routes.GeminiVisionProvider",
        _mock_provider(_VALID_CONTENT),
    ):
        resp = client.post(_ANALYZE_URL, files={"file": _fake_image()})
    assert resp.json()["observations"] == ["The car is red.", "Daylight conditions."]


def test_analyze_response_schema_has_no_extra_fields(client: TestClient) -> None:
    with patch(
        "app.vision.routes.GeminiVisionProvider",
        _mock_provider(_VALID_CONTENT),
    ):
        resp = client.post(_ANALYZE_URL, files={"file": _fake_image()})
    body = resp.json()
    assert set(body.keys()) == {"summary", "detected_objects", "observations"}


# ── Gemini unavailable (missing API key) ──────────────────────────────────────


def test_analyze_returns_503_when_key_missing(client: TestClient) -> None:
    mock_instance = AsyncMock()
    mock_instance.analyze.side_effect = VisionProviderUnavailableError(
        "GEMINI_API_KEY is not configured."
    )
    mock_cls = MagicMock(return_value=mock_instance)
    with patch("app.vision.routes.GeminiVisionProvider", mock_cls):
        resp = client.post(_ANALYZE_URL, files={"file": _fake_image()})
    assert resp.status_code == 503


def test_analyze_503_detail_mentions_key(client: TestClient) -> None:
    mock_instance = AsyncMock()
    mock_instance.analyze.side_effect = VisionProviderUnavailableError(
        "GEMINI_API_KEY is not configured."
    )
    mock_cls = MagicMock(return_value=mock_instance)
    with patch("app.vision.routes.GeminiVisionProvider", mock_cls):
        resp = client.post(_ANALYZE_URL, files={"file": _fake_image()})
    assert "GEMINI_API_KEY" in resp.json()["detail"]


# ── Malformed Gemini response ─────────────────────────────────────────────────


def test_analyze_returns_502_on_malformed_json(client: TestClient) -> None:
    with patch(
        "app.vision.routes.GeminiVisionProvider",
        _mock_provider("not valid json at all"),
    ):
        resp = client.post(_ANALYZE_URL, files={"file": _fake_image()})
    assert resp.status_code == 502


# ── Response does not leak secrets ────────────────────────────────────────────


def test_analyze_response_contains_no_secrets(client: TestClient) -> None:
    with patch(
        "app.vision.routes.GeminiVisionProvider",
        _mock_provider(_VALID_CONTENT),
    ):
        resp = client.post(_ANALYZE_URL, files={"file": _fake_image()})
    body = resp.text.lower()
    assert "secret" not in body
    assert "password" not in body
    assert "api_key" not in body
