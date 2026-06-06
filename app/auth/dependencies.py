"""FastAPI dependencies for authenticated routes."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.security_context import SecurityContext


def get_security_context(request: Request) -> SecurityContext:
    """Return the SecurityContext attached by JWTAuthMiddleware.

    Raises HTTP 401 if the middleware did not attach a context, which guards
    against misconfiguration where a protected route is accidentally excluded
    from middleware coverage.
    """
    ctx = getattr(request.state, "security_context", None)
    if not isinstance(ctx, SecurityContext):
        raise HTTPException(status_code=401, detail="Authentication required")
    return ctx
