from __future__ import annotations

from uuid import UUID

from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class UsageRecord(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Aggregated usage counters per tenant per billing period."""

    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "billing_period",
            "project_id",
            name="uq_usage_tenant_period_project",
        ),
        Index("ix_usage_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_usage_tenant_id_project_id", "tenant_id", "project_id"),
    )

    # YYYY-MM  e.g. "2026-06"
    billing_period: Mapped[str] = mapped_column(String(7))
    project_id: Mapped[UUID | None] = mapped_column(default=None)
    request_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ai_call_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sql_airlock_blocks: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    rate_limit_blocks: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    token_usage: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
