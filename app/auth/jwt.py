"""JWT validation and SecurityContext building.

Security contract
-----------------
- Token payload is NEVER accessed before signature verification.
- ``jwt.decode()`` verifies signature, expiry, issuer, and audience atomically.
- Raw token strings are never logged.
- All parsing failures map to opaque ``TokenExpiredError`` / ``TokenInvalidError``
  — no PyJWT internals leak to callers.

Multi-key verification
----------------------
``validate_token`` tries the *current* signing key first, then the *previous*
key (if one is retained).  The previous key is only tried on signature failures
— expiry, issuer, and audience mismatches are propagated immediately without
retrying, since those failures are not key-specific.

This gives zero-downtime key rotation: tokens signed with the old key remain
valid until they expire after ``KeyRotationService.promote_new_key()`` is
called.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    MissingRequiredClaimError,
)

from app.core.config import settings
from app.core.security_context import SecurityContext

if TYPE_CHECKING:
    from app.secrets.rotation import KeyRotationService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TokenError(Exception):
    """Base for all token validation failures."""


class TokenExpiredError(TokenError):
    """Token is structurally valid but past its expiry time."""


class TokenInvalidError(TokenError):
    """Any other validation failure (bad signature, wrong issuer, etc.)."""


# ---------------------------------------------------------------------------
# Verified claims — only ever built from a verified payload
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifiedClaims:
    """Claims extracted from a fully verified JWT.

    Never constructed from raw/unverified data.
    """

    subject: UUID
    tenant_id: UUID
    roles: frozenset[str]
    permissions: frozenset[str]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_token(
    token: str,
    *,
    rotation_service: KeyRotationService | None = None,
) -> VerifiedClaims:
    """Decode and fully verify a JWT, returning verified claims.

    Tries verification keys in order: [current, previous (if any)].
    Signature failures on the current key trigger a retry with the previous
    key — all other failures (expired, wrong issuer, wrong audience) are
    raised immediately without retry.

    Parameters
    ----------
    token:
        Raw Bearer token string — never logged.
    rotation_service:
        Override the default process-wide ``KeyRotationService``.  Pass an
        explicit instance in tests to avoid mutating the module-level singleton.
    """
    if rotation_service is None:
        from app.secrets.rotation import get_rotation_service

        rotation_service = get_rotation_service()

    keys: list[str] = [rotation_service.get_current_key()]
    prev = rotation_service.get_previous_key()
    if prev is not None:
        keys.append(prev)

    last_sig_error: Exception | None = None

    for key in keys:
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=[settings.JWT_ALGORITHM],
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
                issuer=settings.JWT_ISSUER,
                audience=settings.JWT_AUDIENCE,
            )
            return _extract_claims(payload)
        except ExpiredSignatureError as exc:
            # Expiry is independent of the signing key — don't retry.
            logger.info("JWT rejected: expired")
            raise TokenExpiredError("Token has expired") from exc
        except InvalidSignatureError as exc:
            # Signature mismatch — try the next key if one is available.
            last_sig_error = exc
            continue
        except (
            InvalidIssuerError,
            InvalidAudienceError,
            MissingRequiredClaimError,
            DecodeError,
            InvalidTokenError,
        ) as exc:
            # Non-signature structural failures — no point retrying.
            logger.info("JWT rejected: %s", type(exc).__name__)
            raise TokenInvalidError("Invalid authentication token") from exc

    # All keys exhausted (always at least the current key was tried).
    logger.info("JWT rejected: signature mismatch on all available keys")
    raise TokenInvalidError("Invalid authentication token") from last_sig_error


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _as_str_frozenset(value: object) -> frozenset[str]:
    if isinstance(value, list):
        return frozenset(item for item in value if isinstance(item, str))
    return frozenset()


def _extract_claims(payload: dict[str, Any]) -> VerifiedClaims:
    """Extract and validate custom claims from a verified payload.

    Only called after ``jwt.decode()`` has verified the signature.
    """
    try:
        subject = UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise TokenInvalidError("Token 'sub' claim is not a valid UUID") from exc

    try:
        tenant_id = UUID(str(payload["tenant_id"]))
    except (ValueError, KeyError) as exc:
        raise TokenInvalidError("Token missing or invalid 'tenant_id' claim") from exc

    roles = _as_str_frozenset(payload.get("roles"))
    permissions = _as_str_frozenset(payload.get("permissions"))

    return VerifiedClaims(
        subject=subject,
        tenant_id=tenant_id,
        roles=roles,
        permissions=permissions,
    )


# ---------------------------------------------------------------------------
# SecurityContext builder
# ---------------------------------------------------------------------------


def build_security_context(
    claims: VerifiedClaims,
    *,
    request_id: UUID | None = None,
) -> SecurityContext:
    """Build a SecurityContext from verified JWT claims.

    A fresh request_id UUID is generated for each request when not supplied,
    providing per-request traceability without relying on token-embedded IDs.
    """
    return SecurityContext(
        request_id=request_id or uuid4(),
        current_user_id=claims.subject,
        tenant_id=claims.tenant_id,
        roles=claims.roles,
        permissions=claims.permissions,
    )
