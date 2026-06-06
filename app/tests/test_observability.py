"""Tests for the observability layer: metrics, request-id, header redaction."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.observability.middleware import _normalize_path, _redact_headers
from app.observability.tracing import setup_tracing

# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_200(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_metrics_content_type_is_plain_text(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_metrics_contain_mythos_prefix(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert "mythos_" in response.text


@pytest.mark.asyncio
async def test_metrics_no_user_id_label(client: AsyncClient) -> None:
    await client.get("/health")
    response = await client.get("/metrics")
    assert "user_id" not in response.text


@pytest.mark.asyncio
async def test_metrics_no_tenant_id_label(client: AsyncClient) -> None:
    await client.get("/health")
    response = await client.get("/metrics")
    assert "tenant_id" not in response.text


@pytest.mark.asyncio
async def test_metrics_http_requests_counter_present(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert "mythos_http_requests_total" in response.text


@pytest.mark.asyncio
async def test_metrics_http_duration_histogram_present(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert "mythos_http_request_duration_seconds" in response.text


# ---------------------------------------------------------------------------
# X-Request-ID header propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_x_request_id_header_present_in_response(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_client_supplied_request_id_is_preserved(client: AsyncClient) -> None:
    rid = "123e4567-e89b-12d3-a456-426614174000"
    response = await client.get("/health", headers={"X-Request-ID": rid})
    assert response.headers["x-request-id"] == rid


@pytest.mark.asyncio
async def test_invalid_request_id_gets_new_uuid(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "not-a-uuid"})
    rid = response.headers.get("x-request-id", "")
    assert len(rid) == 36
    assert rid != "not-a-uuid"


# ---------------------------------------------------------------------------
# Header redaction (unit tests — no HTTP required)
# ---------------------------------------------------------------------------


def test_redact_authorization_header() -> None:
    redacted = _redact_headers({"Authorization": "Bearer supersecret"})
    assert redacted["Authorization"] == "[REDACTED]"


def test_redact_cookie_header() -> None:
    redacted = _redact_headers({"Cookie": "session=abc123"})
    assert redacted["Cookie"] == "[REDACTED]"


def test_redact_set_cookie_header() -> None:
    redacted = _redact_headers({"Set-Cookie": "id=xyz"})
    assert redacted["Set-Cookie"] == "[REDACTED]"


def test_redact_header_containing_token_keyword() -> None:
    redacted = _redact_headers({"x-access-token": "foo"})
    assert redacted["x-access-token"] == "[REDACTED]"


def test_redact_header_containing_secret_keyword() -> None:
    redacted = _redact_headers({"x-client-secret": "bar"})
    assert redacted["x-client-secret"] == "[REDACTED]"


def test_safe_header_not_redacted() -> None:
    redacted = _redact_headers({"Content-Type": "application/json", "Accept": "*/*"})
    assert redacted["Content-Type"] == "application/json"
    assert redacted["Accept"] == "*/*"


# ---------------------------------------------------------------------------
# Path normalisation (unit tests)
# ---------------------------------------------------------------------------


def test_normalize_path_replaces_uuid() -> None:
    path = "/v1/orders/123e4567-e89b-12d3-a456-426614174000"
    assert _normalize_path(path) == "/v1/orders/{id}"


def test_normalize_path_leaves_non_uuid_intact() -> None:
    assert _normalize_path("/v1/route") == "/v1/route"


def test_normalize_path_multiple_uuids() -> None:
    path = (
        "/a/123e4567-e89b-12d3-a456-426614174000/b/123e4567-e89b-12d3-a456-426614174001"
    )
    assert _normalize_path(path) == "/a/{id}/b/{id}"


# ---------------------------------------------------------------------------
# OTEL disabled — no crash
# ---------------------------------------------------------------------------


def test_otel_disabled_setup_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.observability.tracing.settings.OTEL_ENABLED", False)
    setup_tracing(None)  # must not raise
