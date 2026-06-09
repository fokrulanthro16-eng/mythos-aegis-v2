"""Operational and Kubernetes-style health endpoints.

Top-level operational endpoints (no auth required):
  GET /health  — simple liveness signal for load balancers
  GET /status  — richer status with version, database, and Redis probe

Kubernetes sub-path probes (no auth required):
  GET /health/live     — liveness probe  (process alive)
  GET /health/ready    — readiness probe (database reachable)
  GET /health/startup  — startup probe   (app initialised)

Responses intentionally contain no sensitive data.
"""

from __future__ import annotations

import subprocess

import redis.asyncio as aioredis
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette import status

from app.core.config import settings
from app.db.session import health_check


def _get_version() -> str:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        v = result.stdout.strip()
        return v if v else "unknown"
    except Exception:
        return "unknown"


_VERSION: str = _get_version()


async def _redis_ping() -> str:
    try:
        client: aioredis.Redis = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        await client.ping()
        await client.aclose()
        return "connected"
    except Exception:
        return "disconnected"


# Top-level operational routes — no URL prefix.
ops_router = APIRouter(tags=["ops"])


@ops_router.get("/health")
async def health_root() -> JSONResponse:
    """Simple liveness signal; always 200 while the process is alive."""
    return JSONResponse({"status": "ok"})


@ops_router.get("/status")
async def service_status() -> JSONResponse:
    """Service status including version, database, and Redis connectivity."""
    db_status = "connected" if await health_check() else "disconnected"
    redis_status = await _redis_ping()
    return JSONResponse(
        {
            "service": settings.OTEL_SERVICE_NAME,
            "version": _VERSION,
            "database": db_status,
            "redis": redis_status,
        }
    )


# Kubernetes sub-path probes.
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
