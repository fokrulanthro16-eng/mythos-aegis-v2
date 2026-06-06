"""Tests for /health/live, /health/ready, /health/startup endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_live_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_live_body_is_ok(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready_returns_200_when_db_healthy(client: AsyncClient) -> None:
    with patch(
        "app.observability.health.health_check", new_callable=AsyncMock
    ) as mock_hc:
        mock_hc.return_value = True
        response = await client.get("/health/ready")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_ready_body_when_db_healthy(client: AsyncClient) -> None:
    with patch(
        "app.observability.health.health_check", new_callable=AsyncMock
    ) as mock_hc:
        mock_hc.return_value = True
        response = await client.get("/health/ready")
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_db_unhealthy(client: AsyncClient) -> None:
    with patch(
        "app.observability.health.health_check", new_callable=AsyncMock
    ) as mock_hc:
        mock_hc.return_value = False
        response = await client.get("/health/ready")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_health_ready_body_when_db_unhealthy(client: AsyncClient) -> None:
    with patch(
        "app.observability.health.health_check", new_callable=AsyncMock
    ) as mock_hc:
        mock_hc.return_value = False
        response = await client.get("/health/ready")
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["database"] == "unreachable"


@pytest.mark.asyncio
async def test_health_startup_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health/startup")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_startup_body_is_non_sensitive(client: AsyncClient) -> None:
    response = await client.get("/health/startup")
    data = response.json()
    assert data["status"] == "started"
    # env is present but never contains secrets (just app env name)
    assert "env" in data
    assert data["env"] in {"development", "staging", "production"}


@pytest.mark.asyncio
async def test_health_ready_body_contains_no_secrets(client: AsyncClient) -> None:
    with patch(
        "app.observability.health.health_check", new_callable=AsyncMock
    ) as mock_hc:
        mock_hc.return_value = True
        response = await client.get("/health/ready")
    body = response.text
    assert "secret" not in body.lower()
    assert "password" not in body.lower()
    assert "token" not in body.lower()


@pytest.mark.asyncio
async def test_health_endpoints_are_public(client: AsyncClient) -> None:
    """Health endpoints must not require JWT authentication."""
    for path in ("/health/live", "/health/ready", "/health/startup"):
        with patch(
            "app.observability.health.health_check", new_callable=AsyncMock
        ) as mock_hc:
            mock_hc.return_value = True
            response = await client.get(path)
        assert response.status_code != 401, f"{path} should be public"
