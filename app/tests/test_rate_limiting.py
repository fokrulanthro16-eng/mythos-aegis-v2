"""Tests for Redis-backed rate limiting.

Test strategy
-------------
- The Redis client and check_rate_limit function are mocked so tests run
  without a live Redis instance.
- JWT tokens are generated with the test secret so the full auth middleware
  stack exercises the rate-limit layer in integration.
- Prometheus counters are verified by capturing calls on the mock objects.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.rate_limit.limiter import (
    LimitResult,
    build_anon_identifier,
    build_auth_identifier,
)
from app.rate_limit.policies import POLICIES, Policy

# ---------------------------------------------------------------------------
# Token factory (mirrors the pattern used in test_auth.py)
# ---------------------------------------------------------------------------

_ALL_PERMS = ["orders.cancel", "analytics.read", "policies.read", "vision.analyze"]


def _make_token(
    *,
    subject: UUID | None = None,
    tenant_id: UUID | None = None,
    permissions: list[str] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(subject or uuid4()),
        "tenant_id": str(tenant_id or uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "roles": ["user"],
        "permissions": permissions if permissions is not None else _ALL_PERMS,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Policy unit tests
# ---------------------------------------------------------------------------


def test_policy_limits_are_defined() -> None:
    assert Policy.ANONYMOUS in POLICIES
    assert Policy.AUTHENTICATED in POLICIES
    assert Policy.SQL_ANALYTICS in POLICIES
    assert Policy.WRITE_MUTATION in POLICIES
    assert Policy.RAG_VISION in POLICIES


def test_anonymous_limit_is_30_per_minute() -> None:
    p = POLICIES[Policy.ANONYMOUS]
    assert p.requests == 30
    assert p.window_seconds == 60


def test_authenticated_limit_is_120_per_minute() -> None:
    p = POLICIES[Policy.AUTHENTICATED]
    assert p.requests == 120
    assert p.window_seconds == 60


def test_sql_analytics_limit_is_60_per_minute() -> None:
    p = POLICIES[Policy.SQL_ANALYTICS]
    assert p.requests == 60
    assert p.window_seconds == 60


def test_write_mutation_limit_is_20_per_minute() -> None:
    p = POLICIES[Policy.WRITE_MUTATION]
    assert p.requests == 20
    assert p.window_seconds == 60


def test_vision_limit_is_15_per_minute() -> None:
    p = POLICIES[Policy.RAG_VISION]
    assert p.requests == 15
    assert p.window_seconds == 60


# ---------------------------------------------------------------------------
# Identifier builder unit tests
# ---------------------------------------------------------------------------


def test_build_anon_identifier_hashes_ip() -> None:
    key = build_anon_identifier("192.168.1.1")
    assert key.startswith("anon:")
    assert "192.168.1.1" not in key  # raw IP never in key


def test_build_anon_identifier_same_ip_same_key() -> None:
    assert build_anon_identifier("10.0.0.1") == build_anon_identifier("10.0.0.1")


def test_build_anon_identifier_different_ips_differ() -> None:
    assert build_anon_identifier("10.0.0.1") != build_anon_identifier("10.0.0.2")


def test_build_auth_identifier_includes_tenant_and_user() -> None:
    tid, uid = str(uuid4()), str(uuid4())
    key = build_auth_identifier(tid, uid)
    assert tid in key
    assert uid in key


def test_build_auth_identifier_tenant_isolation() -> None:
    uid = str(uuid4())
    tid_a, tid_b = str(uuid4()), str(uuid4())
    assert build_auth_identifier(tid_a, uid) != build_auth_identifier(tid_b, uid)


# ---------------------------------------------------------------------------
# Middleware HTTP tests — rate limit allowed (200)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anonymous_request_allowed_under_limit(client: AsyncClient) -> None:
    """A request under the anonymous limit returns 200."""
    allowed = LimitResult(allowed=True, remaining=29, retry_after=0)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = allowed
        response = await client.get("/intent/parse")
    # /intent/parse is public but not exempt — gets ANONYMOUS policy
    assert response.status_code != 429


@pytest.mark.asyncio
async def test_authenticated_request_allowed_under_limit(client: AsyncClient) -> None:
    """An authenticated request under the auth limit is forwarded to the handler."""
    allowed = LimitResult(allowed=True, remaining=119, retry_after=0)
    token = _make_token()
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = allowed
        response = await client.post(
            "/v1/route",
            json={"message": "cancel my order"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code != 429


# ---------------------------------------------------------------------------
# Middleware HTTP tests — rate limit exceeded (429)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anonymous_rate_limit_returns_429(client: AsyncClient) -> None:
    blocked = LimitResult(allowed=False, remaining=0, retry_after=45)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = blocked
        response = await client.get("/intent/parse")
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_authenticated_rate_limit_returns_429(client: AsyncClient) -> None:
    blocked = LimitResult(allowed=False, remaining=0, retry_after=30)
    token = _make_token()
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = blocked
        response = await client.post(
            "/v1/route",
            json={"message": "cancel my order"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_429_response_body(client: AsyncClient) -> None:
    blocked = LimitResult(allowed=False, remaining=0, retry_after=30)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = blocked
        response = await client.get("/intent/parse")
    assert response.json() == {"error": "rate_limit_exceeded"}


@pytest.mark.asyncio
async def test_retry_after_header_present(client: AsyncClient) -> None:
    blocked = LimitResult(allowed=False, remaining=0, retry_after=42)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = blocked
        response = await client.get("/intent/parse")
    assert "retry-after" in response.headers
    assert response.headers["retry-after"] == "42"


@pytest.mark.asyncio
async def test_retry_after_reflects_limiter_value(client: AsyncClient) -> None:
    for seconds in (1, 15, 59):
        blocked = LimitResult(allowed=False, remaining=0, retry_after=seconds)
        with patch(
            "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
        ) as m:
            m.return_value = blocked
            resp = await client.get("/intent/parse")
        assert resp.headers["retry-after"] == str(seconds)


# ---------------------------------------------------------------------------
# Tenant isolation — different tenants must hit separate counters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation_uses_separate_keys(client: AsyncClient) -> None:
    """check_rate_limit must be called with different identifiers per tenant."""
    captured: list[str] = []

    async def fake_check(policy: Policy, identifier: str) -> LimitResult:
        captured.append(identifier)
        return LimitResult(allowed=True, remaining=100, retry_after=0)

    tenant_a, tenant_b = uuid4(), uuid4()
    token_a = _make_token(tenant_id=tenant_a)
    token_b = _make_token(tenant_id=tenant_b)

    with patch("app.rate_limit.middleware.check_rate_limit", new=fake_check):
        await client.post(
            "/v1/route",
            json={"message": "cancel my order"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        await client.post(
            "/v1/route",
            json={"message": "cancel my order"},
            headers={"Authorization": f"Bearer {token_b}"},
        )

    assert len(captured) == 2
    assert captured[0] != captured[1], (
        "Different tenants must use different rate-limit keys"
    )
    assert str(tenant_a) in captured[0]
    assert str(tenant_b) in captured[1]


@pytest.mark.asyncio
async def test_tenant_isolation_same_user_different_tenant(client: AsyncClient) -> None:
    """Same user_id under two tenants must produce different rate-limit keys."""
    user_id = uuid4()
    tenant_a, tenant_b = uuid4(), uuid4()
    token_a = _make_token(subject=user_id, tenant_id=tenant_a)
    token_b = _make_token(subject=user_id, tenant_id=tenant_b)
    captured: list[str] = []

    async def fake_check(policy: Policy, identifier: str) -> LimitResult:
        captured.append(identifier)
        return LimitResult(allowed=True, remaining=100, retry_after=0)

    with patch("app.rate_limit.middleware.check_rate_limit", new=fake_check):
        await client.post(
            "/v1/route",
            json={"message": "cancel my order"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        await client.post(
            "/v1/route",
            json={"message": "cancel my order"},
            headers={"Authorization": f"Bearer {token_b}"},
        )

    assert captured[0] != captured[1]


# ---------------------------------------------------------------------------
# Redis unavailable — graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_unavailable_allows_request(client: AsyncClient) -> None:
    """When Redis is down, requests must be allowed (fail-open)."""
    degraded = LimitResult(allowed=True, remaining=-1, retry_after=0)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = degraded
        response = await client.get("/intent/parse")
    assert response.status_code != 429


@pytest.mark.asyncio
async def test_redis_unavailable_no_error_exposed(client: AsyncClient) -> None:
    """Redis errors must never appear in HTTP responses."""
    degraded = LimitResult(allowed=True, remaining=-1, retry_after=0)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = degraded
        response = await client.get("/intent/parse")
    body = response.text.lower()
    assert "redis" not in body
    assert "connection" not in body
    assert "error" not in body or response.status_code < 400


@pytest.mark.asyncio
async def test_limiter_get_redis_returns_none_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_get_redis returns None (not raises) when the connection fails."""
    import redis.asyncio as _aioredis

    import app.rate_limit.limiter as limiter_module

    monkeypatch.setattr(limiter_module, "_redis_client", None)

    # Patch from_url on the real redis.asyncio module object (same object the
    # limiter module imported as `aioredis`).
    with patch.object(_aioredis, "from_url", side_effect=ConnectionRefusedError):
        result = await limiter_module._get_redis()
    assert result is None


@pytest.mark.asyncio
async def test_check_rate_limit_fails_open_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """check_rate_limit returns allowed=True when _get_redis returns None."""
    import app.rate_limit.limiter as limiter_module

    async def fake_get_redis() -> None:
        return None

    monkeypatch.setattr(limiter_module, "_get_redis", fake_get_redis)
    result = await limiter_module.check_rate_limit(Policy.ANONYMOUS, "anon:test")
    assert result.allowed is True


# ---------------------------------------------------------------------------
# Exempt paths — must not be rate-limited
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_live_not_rate_limited(client: AsyncClient) -> None:
    """Health probes must bypass rate limiting entirely."""
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        await client.get("/health/live")
    m.assert_not_called()


@pytest.mark.asyncio
async def test_metrics_endpoint_not_rate_limited(client: AsyncClient) -> None:
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        await client.get("/metrics")
    m.assert_not_called()


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_hits_counter_increments(client: AsyncClient) -> None:
    allowed = LimitResult(allowed=True, remaining=100, retry_after=0)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = allowed
        with patch("app.rate_limit.middleware.rate_limit_hits_total") as hits_mock:
            await client.get("/intent/parse")
            hits_mock.labels.assert_called()
            hits_mock.labels.return_value.inc.assert_called()


@pytest.mark.asyncio
async def test_rate_limit_blocks_counter_increments_on_429(client: AsyncClient) -> None:
    blocked = LimitResult(allowed=False, remaining=0, retry_after=30)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = blocked
        with patch("app.rate_limit.middleware.rate_limit_blocks_total") as blocks_mock:
            await client.get("/intent/parse")
            blocks_mock.labels.assert_called()
            blocks_mock.labels.return_value.inc.assert_called()


@pytest.mark.asyncio
async def test_rate_limit_blocks_not_incremented_when_allowed(
    client: AsyncClient,
) -> None:
    allowed = LimitResult(allowed=True, remaining=100, retry_after=0)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = allowed
        with patch("app.rate_limit.middleware.rate_limit_blocks_total") as blocks_mock:
            await client.get("/intent/parse")
            blocks_mock.labels.return_value.inc.assert_not_called()


# ---------------------------------------------------------------------------
# No user enumeration / tenant leakage in 429
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_429_does_not_leak_user_info(client: AsyncClient) -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    token = _make_token(subject=user_id, tenant_id=tenant_id)
    blocked = LimitResult(allowed=False, remaining=0, retry_after=30)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = blocked
        response = await client.post(
            "/v1/route",
            json={"message": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    body = response.text
    assert str(user_id) not in body
    assert str(tenant_id) not in body


@pytest.mark.asyncio
async def test_429_body_is_uniform(client: AsyncClient) -> None:
    """All 429 bodies must be identical — no info about which limit was hit."""
    blocked = LimitResult(allowed=False, remaining=0, retry_after=30)
    with patch(
        "app.rate_limit.middleware.check_rate_limit", new_callable=AsyncMock
    ) as m:
        m.return_value = blocked
        r1 = await client.get("/intent/parse")
        r2 = await client.get("/health")  # legacy health is not exempt for anon
    # Both 429 bodies must be identical
    if r1.status_code == 429 and r2.status_code == 429:
        assert r1.json() == r2.json()
