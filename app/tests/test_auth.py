"""Tests for app/auth/ — JWT validation, middleware, and dependencies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import (
    TokenExpiredError,
    TokenInvalidError,
    VerifiedClaims,
    build_security_context,
    validate_token,
)
from app.core.config import settings
from app.core.security_context import SecurityContext
from app.main import app

# ---------------------------------------------------------------------------
# Token factory
# ---------------------------------------------------------------------------

_SUBJECT = uuid4()
_TENANT = uuid4()
_ALL_PERMS = ["orders.cancel", "analytics.read", "policies.read", "vision.analyze"]


def _make_token(
    *,
    subject: UUID | None = None,
    tenant_id: UUID | None = None,
    permissions: list[str] | None = None,
    roles: list[str] | None = None,
    expired: bool = False,
    issuer: str | None = None,
    audience: str | list[str] | None = None,
    secret: str | None = None,
    omit_claims: list[str] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(subject or _SUBJECT),
        "tenant_id": str(tenant_id or _TENANT),
        "iss": issuer if issuer is not None else settings.JWT_ISSUER,
        "aud": audience if audience is not None else settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now - timedelta(seconds=1) if expired else now + timedelta(hours=1),
        "roles": roles if roles is not None else ["user"],
        "permissions": permissions if permissions is not None else _ALL_PERMS,
    }
    for claim in omit_claims or []:
        payload.pop(claim, None)
    return jwt.encode(
        payload,
        secret if secret is not None else settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


# ---------------------------------------------------------------------------
# validate_token — success path
# ---------------------------------------------------------------------------


def test_valid_jwt_accepted() -> None:
    token = _make_token()
    claims = validate_token(token)
    assert isinstance(claims, VerifiedClaims)
    assert claims.subject == _SUBJECT
    assert claims.tenant_id == _TENANT
    assert "orders.cancel" in claims.permissions


# ---------------------------------------------------------------------------
# validate_token — expiry
# ---------------------------------------------------------------------------


def test_expired_jwt_rejected() -> None:
    token = _make_token(expired=True)
    with pytest.raises(TokenExpiredError):
        validate_token(token)


# ---------------------------------------------------------------------------
# validate_token — issuer / audience
# ---------------------------------------------------------------------------


def test_invalid_issuer_rejected() -> None:
    token = _make_token(issuer="evil-issuer")
    with pytest.raises(TokenInvalidError):
        validate_token(token)


def test_invalid_audience_rejected() -> None:
    token = _make_token(audience="wrong-audience")
    with pytest.raises(TokenInvalidError):
        validate_token(token)


# ---------------------------------------------------------------------------
# validate_token — signature
# ---------------------------------------------------------------------------


def test_invalid_signature_rejected() -> None:
    token = _make_token(secret="wrong-secret-key")
    with pytest.raises(TokenInvalidError):
        validate_token(token)


def test_tampered_token_rejected() -> None:
    token = _make_token()
    # Flip one character in the signature segment (last part after final '.')
    parts = token.split(".")
    parts[-1] = parts[-1][:-1] + ("A" if parts[-1][-1] != "A" else "B")
    tampered = ".".join(parts)
    with pytest.raises(TokenInvalidError):
        validate_token(tampered)


# ---------------------------------------------------------------------------
# validate_token — missing / malformed claims
# ---------------------------------------------------------------------------


def test_missing_tenant_id_rejected() -> None:
    token = _make_token(omit_claims=["tenant_id"])
    with pytest.raises(TokenInvalidError):
        validate_token(token)


def test_invalid_subject_uuid_rejected() -> None:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": "not-a-uuid",
        "tenant_id": str(uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "roles": ["user"],
        "permissions": [],
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(TokenInvalidError):
        validate_token(token)


def test_missing_required_claim_exp_rejected() -> None:
    token = _make_token(omit_claims=["exp"])
    with pytest.raises(TokenInvalidError):
        validate_token(token)


# ---------------------------------------------------------------------------
# build_security_context
# ---------------------------------------------------------------------------


def test_build_security_context_maps_claims() -> None:
    token = _make_token()
    claims = validate_token(token)
    ctx = build_security_context(claims)
    assert isinstance(ctx, SecurityContext)
    assert ctx.current_user_id == claims.subject
    assert ctx.tenant_id == claims.tenant_id
    assert ctx.permissions == claims.permissions
    assert ctx.roles == claims.roles


def test_build_security_context_uses_provided_request_id() -> None:
    rid = uuid4()
    token = _make_token()
    claims = validate_token(token)
    ctx = build_security_context(claims, request_id=rid)
    assert ctx.request_id == rid


def test_build_security_context_generates_request_id_when_none() -> None:
    token = _make_token()
    claims = validate_token(token)
    ctx = build_security_context(claims)
    assert ctx.request_id is not None


# ---------------------------------------------------------------------------
# HTTP middleware — endpoint-level auth tests
# ---------------------------------------------------------------------------


async def test_route_endpoint_rejects_missing_token() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/route", json={"message": "hello"})
    assert response.status_code == 401


async def test_route_endpoint_rejects_expired_token() -> None:
    token = _make_token(expired=True)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401
    body = response.json()
    # Token string must never appear in response
    assert token not in str(body)


async def test_route_endpoint_rejects_invalid_token() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "hello"},
            headers={"Authorization": "Bearer garbage.token.value"},
        )
    assert response.status_code == 401


async def test_route_endpoint_accepts_valid_jwt() -> None:
    token = _make_token()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "tell me about my order"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200


async def test_no_token_in_401_response_body() -> None:
    token = _make_token(expired=True)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401
    assert token not in response.text


async def test_raw_jwt_not_returned_to_client() -> None:
    token = _make_token()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "what are my options"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert token not in response.text
