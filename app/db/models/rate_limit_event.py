from __future__ import annotations

from uuid import UUID

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RateLimitEvent(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "rate_limit_events"
    __table_args__ = (
        Index("ix_rate_limit_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_rate_limit_tenant_id_policy_name", "tenant_id", "policy_name"),
    )

    actor_id: Mapped[UUID | None] = mapped_column(default=None)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)
    policy_name: Mapped[str] = mapped_column(String(100))
    endpoint: Mapped[str] = mapped_column(String(255))
    limit_value: Mapped[int] = mapped_column(Integer)
    window_seconds: Mapped[int] = mapped_column(Integer)
    current_count: Mapped[int] = mapped_column(Integer)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, default=None)
