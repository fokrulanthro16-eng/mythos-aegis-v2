from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TenantPlan(StrEnum):
    FREE = "free"
    STARTER = "starter"
    GROWTH = "growth"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class TenantStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        Index("ix_tenant_created_at", "created_at"),
        Index("ix_tenant_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(20), default=TenantPlan.FREE)
    status: Mapped[str] = mapped_column(String(20), default=TenantStatus.TRIAL)
    display_name: Mapped[str | None] = mapped_column(Text, default=None)
