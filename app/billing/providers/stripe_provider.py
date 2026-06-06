"""Stripe billing provider.

Only instantiated when BILLING_PROVIDER=stripe.  The ``stripe`` package is a
lazy import so the application starts without it installed.  STRIPE_SECRET_KEY
is read in __init__ and BillingProviderError is raised immediately if absent.

No secrets are logged.  The Stripe API key is set on the module-level stripe
object and is never echoed to any logger.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.billing.models import PlanTier
from app.billing.providers.base import (
    AbstractBillingProvider,
    CheckoutSession,
    InvoiceInfo,
    SubscriptionInfo,
    WebhookEvent,
)
from app.core.config import settings
from app.core.exceptions import BillingProviderError

logger = logging.getLogger(__name__)

# Price IDs must be configured in .env for production.
_PLAN_PRICE_IDS: dict[PlanTier, str] = {
    PlanTier.FREE: "",
    PlanTier.PRO: "price_pro_placeholder",
    PlanTier.BUSINESS: "price_business_placeholder",
    PlanTier.ENTERPRISE: "price_enterprise_placeholder",
}


def _ts_to_dt(ts: int | float | None) -> datetime:
    if ts is None:
        return datetime.now(tz=UTC)
    return datetime.fromtimestamp(float(ts), tz=UTC)


def _safe_plan(metadata: dict[str, Any] | None) -> PlanTier:
    raw = (metadata or {}).get("plan", "")
    try:
        return PlanTier(raw)
    except ValueError:
        return PlanTier.FREE


class StripeBillingProvider(AbstractBillingProvider):
    """Stripe implementation.  Requires STRIPE_SECRET_KEY to be set."""

    def __init__(self) -> None:
        key = settings.STRIPE_SECRET_KEY
        if not key:
            raise BillingProviderError(
                "STRIPE_SECRET_KEY must be set when BILLING_PROVIDER=stripe. "
                "Switch to BILLING_PROVIDER=mock for local development."
            )
        try:
            import stripe as _stripe  # noqa: PLC0415
        except ModuleNotFoundError as exc:
            raise BillingProviderError(
                "stripe package is not installed. Run: pip install stripe"
            ) from exc

        _stripe.api_key = key  # key is never logged
        self._stripe = _stripe
        logger.info("billing.stripe.provider.initialized")

    async def create_checkout_session(
        self,
        tenant_id: UUID,
        plan: PlanTier,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        price_id = _PLAN_PRICE_IDS.get(plan, "")
        if not price_id:
            raise BillingProviderError(
                f"No Stripe price ID configured for plan '{plan}'. "
                "Set STRIPE_PRICE_PRO / STRIPE_PRICE_BUSINESS / "
                "STRIPE_PRICE_ENTERPRISE."
            )
        session = self._stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"tenant_id": str(tenant_id), "plan": str(plan)},
        )
        return CheckoutSession(
            session_id=session.id,
            checkout_url=session.url,
            plan=plan,
            tenant_id=tenant_id,
            expires_at=_ts_to_dt(session.expires_at),
        )

    async def activate_subscription(
        self,
        tenant_id: UUID,
        plan: PlanTier,
        session_id: str,
    ) -> SubscriptionInfo:
        session = self._stripe.checkout.Session.retrieve(session_id)
        sub = self._stripe.Subscription.retrieve(session.subscription)
        return SubscriptionInfo(
            subscription_id=sub.id,
            customer_id=str(sub.customer),
            plan=plan,
            status=sub.status,
            current_period_start=_ts_to_dt(sub.current_period_start),
            current_period_end=_ts_to_dt(sub.current_period_end),
            cancel_at_period_end=bool(sub.cancel_at_period_end),
        )

    async def cancel_subscription(self, subscription_id: str) -> SubscriptionInfo:
        sub = self._stripe.Subscription.modify(
            subscription_id, cancel_at_period_end=True
        )
        plan = _safe_plan(sub.metadata)
        return SubscriptionInfo(
            subscription_id=sub.id,
            customer_id=str(sub.customer),
            plan=plan,
            status=sub.status,
            current_period_start=_ts_to_dt(sub.current_period_start),
            current_period_end=_ts_to_dt(sub.current_period_end),
            cancel_at_period_end=bool(sub.cancel_at_period_end),
        )

    async def get_subscription(self, subscription_id: str) -> SubscriptionInfo:
        sub = self._stripe.Subscription.retrieve(subscription_id)
        plan = _safe_plan(sub.metadata)
        return SubscriptionInfo(
            subscription_id=sub.id,
            customer_id=str(sub.customer),
            plan=plan,
            status=sub.status,
            current_period_start=_ts_to_dt(sub.current_period_start),
            current_period_end=_ts_to_dt(sub.current_period_end),
            cancel_at_period_end=bool(sub.cancel_at_period_end),
        )

    async def generate_invoice(
        self, subscription_id: str, amount_cents: int
    ) -> InvoiceInfo:
        upcoming = self._stripe.Invoice.upcoming(subscription=subscription_id)
        inv = self._stripe.Invoice.retrieve(upcoming.id)
        return _invoice_from_stripe(inv)

    async def list_invoices(self, subscription_id: str) -> list[InvoiceInfo]:
        result = self._stripe.Invoice.list(subscription=subscription_id, limit=100)
        return [_invoice_from_stripe(inv) for inv in result.auto_paging_iter()]

    async def handle_webhook(self, payload: bytes, signature: str) -> WebhookEvent:
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        if not webhook_secret:
            raise BillingProviderError(
                "STRIPE_WEBHOOK_SECRET must be set when BILLING_PROVIDER=stripe"
            )
        try:
            event = self._stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
        except Exception as exc:
            raise BillingProviderError(
                f"Webhook signature verification failed: {exc}"
            ) from exc

        obj_meta = getattr(event.data.object, "metadata", None) or {}
        tenant_id_raw: str | None = obj_meta.get("tenant_id")
        tenant_id = UUID(tenant_id_raw) if tenant_id_raw else None

        return WebhookEvent(
            event_id=event.id,
            event_type=event.type,
            tenant_id=tenant_id,
            timestamp=_ts_to_dt(event.created),
            data={"type": event.type},  # metadata only — no raw payload stored
        )


def _invoice_from_stripe(inv: Any) -> InvoiceInfo:
    return InvoiceInfo(
        invoice_id=inv.id,
        subscription_id=str(inv.subscription or ""),
        amount_cents=int(inv.amount_paid or inv.amount_due or 0),
        currency=str(inv.currency),
        status=str(inv.status),
        invoice_date=_ts_to_dt(inv.created),
        due_date=_ts_to_dt(inv.due_date) if inv.due_date else None,
        invoice_url=getattr(inv, "hosted_invoice_url", None),
    )
