from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, UUIDPrimaryKeyMixin


class BillingSubscription(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "billing_subscriptions"
    __table_args__ = (Index("ix_billing_sub_tenant_status", "tenant_id", "status"),)

    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(255), default=None
    )
    provider_customer_id: Mapped[str | None] = mapped_column(String(255), default=None)
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
