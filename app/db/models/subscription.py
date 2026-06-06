from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SubscriptionPlan(StrEnum):
    FREE = "free"
    STARTER = "starter"
    GROWTH = "growth"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    UNPAID = "unpaid"


class Subscription(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscription_tenant_id", "tenant_id", unique=True),
        Index("ix_subscription_status", "status"),
    )

    plan: Mapped[str] = mapped_column(String(20), default=SubscriptionPlan.FREE)
    status: Mapped[str] = mapped_column(String(20), default=SubscriptionStatus.TRIALING)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # External billing provider reference (e.g. Stripe subscription ID).
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)
