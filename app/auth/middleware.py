"""JWT authentication middleware.

Intercepts every request that targets an authenticated path, validates the
Bearer token, and attaches a SecurityContext to request.state.

Security rules enforced here:
- Raw token strings are never logged.
- 401 responses never echo the token back to the client.
- The request_id is taken from request.state (set by ObservabilityMiddleware
  when it runs first) so the same UUID flows through the whole stack.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth.jwt import (
    TokenExpiredError,
    TokenInvalidError,
    build_security_context,
    validate_token,
)
from app.observability.metrics import auth_failures_total

logger = logging.getLogger(__name__)

# Paths that do not require a JWT.  All other paths are authenticated.
_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/health/live",
        "/health/ready",
        "/health/startup",
        "/intent/parse",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/v1/billing/plans",
    }
)

_BEARER_PREFIX = "Bearer "


def _auth_error(detail: str, failure_type: str) -> JSONResponse:
    auth_failures_total.labels(failure_type=failure_type).inc()
    return JSONResponse(
        status_code=401,
        content={"error": "authentication_error", "detail": detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _request_id(request: Request) -> UUID:
    """Return the request_id set by ObservabilityMiddleware, or a new one."""
    return getattr(request.state, "request_id", None) or uuid4()


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith(_BEARER_PREFIX):
            return _auth_error(
                "Missing or invalid Authorization header", "missing_token"
            )

        token = auth_header[len(_BEARER_PREFIX) :]
        # Log presence only — never the raw token value.
        logger.debug("JWT auth attempt path=%s", request.url.path)

        try:
            claims = validate_token(token)
        except TokenExpiredError:
            return _auth_error("Token has expired", "expired_token")
        except TokenInvalidError:
            return _auth_error("Invalid authentication token", "invalid_token")

        request.state.security_context = build_security_context(
            claims, request_id=_request_id(request)
        )
        return await call_next(request)
