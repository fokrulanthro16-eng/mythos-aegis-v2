"""Rate limit policy definitions.

Each policy names a bucket with a fixed request quota per time window.
All limits are per-(tenant, user) pair — never global-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Policy(StrEnum):
    ANONYMOUS = "anon"
    AUTHENTICATED = "auth"
    SQL_ANALYTICS = "sql"
    WRITE_MUTATION = "write"
    RAG_VISION = "vision"


@dataclass(frozen=True)
class RatePolicy:
    requests: int  # maximum requests allowed per window
    window_seconds: int  # window duration in seconds


POLICIES: dict[Policy, RatePolicy] = {
    Policy.ANONYMOUS: RatePolicy(requests=30, window_seconds=60),
    Policy.AUTHENTICATED: RatePolicy(requests=120, window_seconds=60),
    Policy.SQL_ANALYTICS: RatePolicy(requests=60, window_seconds=60),
    Policy.WRITE_MUTATION: RatePolicy(requests=20, window_seconds=60),
    Policy.RAG_VISION: RatePolicy(requests=15, window_seconds=60),
}
