"""Mock billing provider — no external dependencies required.

All operations succeed and return realistic-looking fake data.  State is stored
on the instance so each provider instance starts fresh — important for test
isolation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.billing.models import PlanTier
from app.billing.providers.base import (
    AbstractBillingProvider,
    CheckoutSession,
    InvoiceInfo,
    SubscriptionInfo,
    WebhookEvent,
)
from app.core.exceptions import BillingError

logger = logging.getLogger(__name__)

_CHECKOUT_BASE = "http://localhost:8000/mock-billing/checkout"
_INVOICE_BASE = "http://localhost:8000/mock-billing/invoices"


def _now() -> datetime:
    return datetime.now(tz=UTC)


class MockBillingProvider(AbstractBillingProvider):
    """In-memory billing provider for local development and tests."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, SubscriptionInfo] = {}
        self._invoices: dict[str, list[InvoiceInfo]] = {}
        self._sessions: dict[str, CheckoutSession] = {}

    async def create_checkout_session(
        self,
        tenant_id: UUID,
        plan: PlanTier,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        session_id = f"mock_cs_{uuid4().hex[:20]}"
        session = CheckoutSession(
            session_id=session_id,
            checkout_url=f"{_CHECKOUT_BASE}/{session_id}?plan={plan}",
            plan=plan,
            tenant_id=tenant_id,
            expires_at=_now() + timedelta(hours=1),
        )
        self._sessions[session_id] = session
        logger.info(
            "billing.mock.checkout.created session=%s plan=%s tenant=%s",
            session_id,
            plan,
            tenant_id,
        )
        return session

    async def activate_subscription(
        self,
        tenant_id: UUID,
        plan: PlanTier,
        session_id: str,
    ) -> SubscriptionInfo:
        if session_id not in self._sessions and not session_id.startswith("mock_cs_"):
            raise BillingError(f"Unknown checkout session: {session_id!r}")

        sub_id = f"mock_sub_{uuid4().hex[:20]}"
        customer_id = (
            f"mock_cus_{hashlib.sha256(str(tenant_id).encode()).hexdigest()[:20]}"
        )
        now = _now()
        info = SubscriptionInfo(
            subscription_id=sub_id,
            customer_id=customer_id,
            plan=plan,
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
        )
        self._subscriptions[sub_id] = info
        self._invoices[sub_id] = []
        logger.info(
            "billing.mock.subscription.activated sub=%s plan=%s tenant=%s",
            sub_id,
            plan,
            tenant_id,
        )
        return info

    async def cancel_subscription(self, subscription_id: str) -> SubscriptionInfo:
        if subscription_id not in self._subscriptions:
            raise BillingError(f"Subscription not found: {subscription_id!r}")

        info = self._subscriptions[subscription_id]
        updated = info.model_copy(
            update={"status": "cancelled", "cancel_at_period_end": True}
        )
        self._subscriptions[subscription_id] = updated
        logger.info("billing.mock.subscription.cancelled sub=%s", subscription_id)
        return updated

    async def get_subscription(self, subscription_id: str) -> SubscriptionInfo:
        if subscription_id not in self._subscriptions:
            raise BillingError(f"Subscription not found: {subscription_id!r}")
        return self._subscriptions[subscription_id]

    async def generate_invoice(
        self, subscription_id: str, amount_cents: int
    ) -> InvoiceInfo:
        if subscription_id not in self._subscriptions:
            raise BillingError(f"Subscription not found: {subscription_id!r}")

        inv_id = f"mock_inv_{uuid4().hex[:20]}"
        now = _now()
        invoice = InvoiceInfo(
            invoice_id=inv_id,
            subscription_id=subscription_id,
            amount_cents=amount_cents,
            currency="usd",
            status="paid",
            invoice_date=now,
            due_date=now + timedelta(days=30),
            invoice_url=f"{_INVOICE_BASE}/{inv_id}",
        )
        self._invoices[subscription_id].append(invoice)
        logger.info(
            "billing.mock.invoice.generated inv=%s sub=%s amount=%d",
            inv_id,
            subscription_id,
            amount_cents,
        )
        return invoice

    async def list_invoices(self, subscription_id: str) -> list[InvoiceInfo]:
        return list(self._invoices.get(subscription_id, []))

    async def handle_webhook(self, payload: bytes, signature: str) -> WebhookEvent:
        try:
            data: dict[str, str] = json.loads(payload)
        except Exception as exc:
            raise BillingError("Invalid webhook payload: expected JSON") from exc

        event_type = str(data.get("type", "mock.event"))
        tenant_id_raw = data.get("tenant_id")
        tenant_id = UUID(tenant_id_raw) if tenant_id_raw else None

        event = WebhookEvent(
            event_id=f"mock_evt_{uuid4().hex[:20]}",
            event_type=event_type,
            tenant_id=tenant_id,
            timestamp=_now(),
            data=dict(data),
        )
        logger.info("billing.mock.webhook.received type=%s", event_type)
        return event
