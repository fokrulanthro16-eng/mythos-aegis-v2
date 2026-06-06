"""Request observability middleware.

Responsibilities
----------------
1. Generate a UUID request_id (or adopt one supplied via X-Request-ID header).
2. Store it in ``request.state.request_id`` so downstream middleware and
   handlers (including JWTAuthMiddleware) can access it.
3. Log a structured request/response record with timing — sensitive headers
   are redacted before anything is logged.
4. Record HTTP request count and latency in Prometheus.
5. Echo the request_id back in the ``X-Request-ID`` response header.

Security rules
--------------
- Authorization, Cookie, Set-Cookie, and any header whose name contains
  the words jwt, password, token, or secret are replaced with ``[REDACTED]``.
- The request body and URL query parameters are never logged.
"""

from __future__ import annotations

import logging
import re
import time
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.observability.metrics import http_request_duration_seconds, http_requests_total

logger = logging.getLogger(__name__)

# Paths excluded from Prometheus metric recording (high-frequency / meta paths).
_METRICS_EXCLUDED: frozenset[str] = frozenset({"/metrics"})

# Headers whose values must never appear in logs.
_SENSITIVE_NAMES: frozenset[str] = frozenset(
    {"authorization", "cookie", "set-cookie", "x-api-key", "x-auth-token"}
)
_SENSITIVE_KEYWORDS: tuple[str, ...] = ("jwt", "password", "token", "secret")

# Matches UUID v4 path segments so they can be normalised for metric labels.
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of *headers* with sensitive values replaced by ``[REDACTED]``."""
    out: dict[str, str] = {}
    for name, value in headers.items():
        lower = name.lower()
        if lower in _SENSITIVE_NAMES or any(kw in lower for kw in _SENSITIVE_KEYWORDS):
            out[name] = "[REDACTED]"
        else:
            out[name] = value
    return out


def _normalize_path(path: str) -> str:
    """Replace UUID segments with ``{id}`` to keep metric label cardinality low."""
    return _UUID_RE.sub("{id}", path)


def _extract_request_id(request: Request) -> UUID:
    """Return the client-supplied X-Request-ID (if a valid UUID) or a fresh one."""
    raw = request.headers.get("X-Request-ID", "")
    try:
        return UUID(raw)
    except (ValueError, AttributeError):
        return uuid4()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Outer middleware: request-id propagation, timing, metrics, header redaction."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = _extract_request_id(request)
        request.state.request_id = request_id

        path = request.url.path
        method = request.method
        start = time.perf_counter()

        logger.debug(
            "→ %s %s",
            method,
            path,
            extra={
                "request_id": str(request_id),
                "headers": _redact_headers(dict(request.headers)),
            },
        )

        response = await call_next(request)

        duration = time.perf_counter() - start
        status_code = str(response.status_code)

        logger.debug(
            "← %s %s %s (%.1fms)",
            method,
            path,
            status_code,
            duration * 1000,
            extra={
                "request_id": str(request_id),
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 1),
            },
        )

        if path not in _METRICS_EXCLUDED:
            endpoint = _normalize_path(path)
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
            ).inc()
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

        response.headers["X-Request-ID"] = str(request_id)
        return response
