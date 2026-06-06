"""Abstract billing provider contract and provider-layer data transfer objects.

All provider implementations must satisfy this interface.  The DTOs defined
here are provider-layer types — they are translated into DB models and API
schemas by BillingService.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.billing.models import PlanTier


class CheckoutSession(BaseModel):
    session_id: str
    checkout_url: str
    plan: PlanTier
    tenant_id: UUID
    expires_at: datetime


class SubscriptionInfo(BaseModel):
    subscription_id: str
    customer_id: str
    plan: PlanTier
    status: str  # active | cancelled | past_due | trialing
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool


class InvoiceInfo(BaseModel):
    invoice_id: str
    subscription_id: str
    amount_cents: int
    currency: str
    status: str  # paid | open | void | uncollectible
    invoice_date: datetime
    due_date: datetime | None
    invoice_url: str | None


class WebhookEvent(BaseModel):
    event_id: str
    event_type: str
    tenant_id: UUID | None
    timestamp: datetime
    data: dict[str, Any]


class AbstractBillingProvider(ABC):
    """Contract all billing providers must implement."""

    @abstractmethod
    async def create_checkout_session(
        self,
        tenant_id: UUID,
        plan: PlanTier,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession: ...

    @abstractmethod
    async def activate_subscription(
        self,
        tenant_id: UUID,
        plan: PlanTier,
        session_id: str,
    ) -> SubscriptionInfo: ...

    @abstractmethod
    async def cancel_subscription(
        self,
        subscription_id: str,
    ) -> SubscriptionInfo: ...

    @abstractmethod
    async def get_subscription(
        self,
        subscription_id: str,
    ) -> SubscriptionInfo: ...

    @abstractmethod
    async def generate_invoice(
        self,
        subscription_id: str,
        amount_cents: int,
    ) -> InvoiceInfo: ...

    @abstractmethod
    async def list_invoices(
        self,
        subscription_id: str,
    ) -> list[InvoiceInfo]: ...

    @abstractmethod
    async def handle_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent: ...
