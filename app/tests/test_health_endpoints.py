"""Tests for /health, /status, and /health/* endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

_HEALTH_CHECK = "app.observability.health.health_check"
_REDIS_PING = "app.observability.health._redis_ping"


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


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_root_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_root_body(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_root_is_public(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code != 401


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_returns_200(client: AsyncClient) -> None:
    with (
        patch(_HEALTH_CHECK, new_callable=AsyncMock) as mock_db,
        patch(_REDIS_PING, new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = "connected"
        response = await client.get("/status")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_service_field(client: AsyncClient) -> None:
    with (
        patch(_HEALTH_CHECK, new_callable=AsyncMock) as mock_db,
        patch(_REDIS_PING, new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = "connected"
        response = await client.get("/status")
    assert response.json()["service"] == "mythos-aegis"


@pytest.mark.asyncio
async def test_status_version_is_string(client: AsyncClient) -> None:
    with (
        patch(_HEALTH_CHECK, new_callable=AsyncMock) as mock_db,
        patch(_REDIS_PING, new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = "connected"
        response = await client.get("/status")
    assert isinstance(response.json()["version"], str)
    assert response.json()["version"] != ""


@pytest.mark.asyncio
async def test_status_database_connected(client: AsyncClient) -> None:
    with (
        patch(_HEALTH_CHECK, new_callable=AsyncMock) as mock_db,
        patch(_REDIS_PING, new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = "connected"
        response = await client.get("/status")
    assert response.json()["database"] == "connected"


@pytest.mark.asyncio
async def test_status_database_disconnected(client: AsyncClient) -> None:
    with (
        patch(_HEALTH_CHECK, new_callable=AsyncMock) as mock_db,
        patch(_REDIS_PING, new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = False
        mock_redis.return_value = "disconnected"
        response = await client.get("/status")
    assert response.json()["database"] == "disconnected"


@pytest.mark.asyncio
async def test_status_redis_connected(client: AsyncClient) -> None:
    with (
        patch(_HEALTH_CHECK, new_callable=AsyncMock) as mock_db,
        patch(_REDIS_PING, new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = "connected"
        response = await client.get("/status")
    assert response.json()["redis"] == "connected"


@pytest.mark.asyncio
async def test_status_redis_disconnected(client: AsyncClient) -> None:
    with (
        patch(_HEALTH_CHECK, new_callable=AsyncMock) as mock_db,
        patch(_REDIS_PING, new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = "disconnected"
        response = await client.get("/status")
    assert response.json()["redis"] == "disconnected"


@pytest.mark.asyncio
async def test_status_is_public(client: AsyncClient) -> None:
    with (
        patch(_HEALTH_CHECK, new_callable=AsyncMock) as mock_db,
        patch(_REDIS_PING, new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = "connected"
        response = await client.get("/status")
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_status_contains_no_secrets(client: AsyncClient) -> None:
    with (
        patch(_HEALTH_CHECK, new_callable=AsyncMock) as mock_db,
        patch(_REDIS_PING, new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = "connected"
        response = await client.get("/status")
    body = response.text
    assert "secret" not in body.lower()
    assert "password" not in body.lower()
    assert "token" not in body.lower()
    assert "key" not in body.lower()
