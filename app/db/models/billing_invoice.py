from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, UUIDPrimaryKeyMixin


class BillingInvoice(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "billing_invoices"
    __table_args__ = (
        Index("ix_billing_invoice_tenant_date", "tenant_id", "invoice_date"),
    )

    subscription_id: Mapped[UUID] = mapped_column(nullable=False)
    provider_invoice_id: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), default="usd", server_default="usd"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    invoice_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    invoice_url: Mapped[str | None] = mapped_column(String(2048), default=None)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
