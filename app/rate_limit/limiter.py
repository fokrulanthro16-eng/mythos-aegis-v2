"""Redis-backed fixed-window rate limiter.

Design rules
------------
- Fail-open: if Redis is unreachable, requests are allowed and a warning is
  logged.  The application never becomes unavailable due to Redis outage.
- Keys always include a scoped identifier (tenant+user or hashed IP).  There
  are no global-only counters.
- Client IP is one-way-hashed before use as a Redis key so raw IPs are never
  persisted in Redis.
- Redis errors are caught and logged; they are never surfaced to callers.
"""

from __future__ import annotations

import hashlib
import logging
from typing import NamedTuple

import redis.asyncio as aioredis

from app.core.config import settings
from app.rate_limit.policies import POLICIES, Policy

logger = logging.getLogger(__name__)

# Atomic fixed-window counter script.
# Returns [current_count, ttl_seconds].
# Sets EXPIRE only on the first increment so the window resets cleanly.
_LUA_INCR = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""

_redis_client: aioredis.Redis | None = None


class LimitResult(NamedTuple):
    allowed: bool
    remaining: int  # requests left in the current window (-1 = unknown / degraded)
    retry_after: int  # seconds until the window resets; 0 when allowed


async def _get_redis() -> aioredis.Redis | None:
    """Return the shared async Redis client, initialising it on first call.

    Returns None (without raising) if Redis is unavailable.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        client: aioredis.Redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        await client.ping()
        _redis_client = client
        logger.info("Redis connected for rate limiting: %s", settings.REDIS_URL)
        return _redis_client
    except Exception as exc:
        logger.warning(
            "Redis unavailable — rate limiting degraded gracefully: %s",
            type(exc).__name__,
        )
        return None


def build_anon_identifier(ip: str) -> str:
    """One-way-hashed anonymous identifier derived from the client IP address."""
    return "anon:" + hashlib.sha256(ip.encode()).hexdigest()[:16]


def build_auth_identifier(tenant_id: str, user_id: str) -> str:
    """Scoped identifier for an authenticated user.

    Always includes both tenant_id and user_id — never a global-only key.
    """
    return f"{tenant_id}:{user_id}"


async def check_rate_limit(policy: Policy, identifier: str) -> LimitResult:
    """Increment and check the rate limit counter for (policy, identifier).

    Fails-open: returns ``LimitResult(allowed=True)`` when Redis is unreachable
    or raises an unexpected error — availability takes precedence over strict
    rate enforcement when the data store is down.
    """
    client = await _get_redis()
    if client is None:
        return LimitResult(allowed=True, remaining=-1, retry_after=0)

    cfg = POLICIES[policy]
    key = f"rl:{policy}:{identifier}"

    try:
        script = client.register_script(_LUA_INCR)
        raw: list[int] = await script(keys=[key], args=[cfg.window_seconds])
        count, ttl = raw[0], raw[1]
        safe_ttl = ttl if ttl > 0 else cfg.window_seconds
        if count > cfg.requests:
            return LimitResult(allowed=False, remaining=0, retry_after=safe_ttl)
        return LimitResult(
            allowed=True,
            remaining=max(0, cfg.requests - count),
            retry_after=0,
        )
    except Exception as exc:
        logger.warning(
            "Redis rate-limit check error — allowing request: %s",
            type(exc).__name__,
        )
        return LimitResult(allowed=True, remaining=-1, retry_after=0)


async def close_redis() -> None:
    """Close the Redis connection pool (called during application shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
