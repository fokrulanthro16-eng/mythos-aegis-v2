from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TimestampMixin, UUIDPrimaryKeyMixin


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class SystemHealthSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Point-in-time snapshot of system health.  Not tenant-scoped."""

    __tablename__ = "system_health_snapshots"
    __table_args__ = (Index("ix_health_snapshot_created_at", "created_at"),)

    overall_status: Mapped[str] = mapped_column(
        String(20), default=HealthStatus.HEALTHY
    )
    api_latency_ms: Mapped[float | None] = mapped_column(Float, default=None)
    db_latency_ms: Mapped[float | None] = mapped_column(Float, default=None)
    active_tenants: Mapped[int | None] = mapped_column(Integer, default=None)
    requests_last_hour: Mapped[int | None] = mapped_column(Integer, default=None)
    cpu_percent: Mapped[float | None] = mapped_column(Float, default=None)
    memory_percent: Mapped[float | None] = mapped_column(Float, default=None)
    error_rate_percent: Mapped[float | None] = mapped_column(Float, default=None)
