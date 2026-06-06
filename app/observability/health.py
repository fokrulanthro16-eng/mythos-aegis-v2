"""Kubernetes-style health endpoints.

GET /health/live     — liveness probe  (process alive)
GET /health/ready    — readiness probe (database reachable)
GET /health/startup  — startup probe   (app initialised)

Responses intentionally contain no sensitive data: no stack traces, no
configuration values, no user or tenant information.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette import status

from app.core.config import settings
from app.db.session import health_check

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> JSONResponse:
    """Always returns 200 while the process is alive."""
    return JSONResponse({"status": "ok"})


@router.get("/ready")
async def readiness() -> JSONResponse:
    """Returns 200 when the database is reachable, 503 otherwise."""
    db_ok = await health_check()
    if db_ok:
        return JSONResponse({"status": "ready", "database": "ok"})
    return JSONResponse(
        {"status": "unavailable", "database": "unreachable"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@router.get("/startup")
async def startup_check() -> JSONResponse:
    """Returns 200 once the application has finished initialising."""
    return JSONResponse({"status": "started", "env": settings.APP_ENV})
