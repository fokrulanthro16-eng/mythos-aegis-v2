"""Rate limiting middleware.

Execution position in the middleware stack
------------------------------------------
ObservabilityMiddleware (outermost) → JWTAuthMiddleware → RateLimitMiddleware → handler

RateLimitMiddleware runs after JWT auth so it can read request.state.security_context
to scope limits to (tenant_id, user_id) for authenticated requests.

Security rules
--------------
- 429 responses are identical regardless of which user/tenant triggered them.
  This prevents user-enumeration via rate-limit behaviour.
- Redis errors and key internals are never surfaced to clients.
- Health probes and infrastructure endpoints are exempt (Kubernetes probes
  must not be throttled).
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.observability.metrics import rate_limit_blocks_total, rate_limit_hits_total
from app.rate_limit.limiter import (
    LimitResult,
    build_anon_identifier,
    build_auth_identifier,
    check_rate_limit,
)
from app.rate_limit.policies import Policy

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting.
# Health probes must never be throttled (Kubernetes liveness/readiness/startup).
# Prometheus scraper and API schema docs are also exempt.
_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/health/live",
        "/health/ready",
        "/health/startup",
        "/status",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)

_FALLBACK_IP = "unknown"


def _client_ip(request: Request) -> str:
    """Extract the most-specific client IP available."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return _FALLBACK_IP


def _rate_limit_exceeded(retry_after: int) -> Response:
    """Return a uniform 429 response — no user/tenant information leaked."""
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded"},
        headers={"Retry-After": str(retry_after)},
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        ctx = getattr(request.state, "security_context", None)

        if ctx is not None:
            # Authenticated: scope limit to (tenant_id, user_id).
            policy = Policy.AUTHENTICATED
            identifier = build_auth_identifier(
                str(ctx.tenant_id), str(ctx.current_user_id)
            )
        else:
            # Anonymous: scope limit to hashed client IP.
            policy = Policy.ANONYMOUS
            identifier = build_anon_identifier(_client_ip(request))

        result: LimitResult = await check_rate_limit(policy, identifier)

        rate_limit_hits_total.labels(policy=policy).inc()

        if not result.allowed:
            rate_limit_blocks_total.labels(policy=policy).inc()
            logger.info(
                "Rate limit exceeded policy=%s retry_after=%s",
                policy,
                result.retry_after,
            )
            return _rate_limit_exceeded(result.retry_after)

        return await call_next(request)
