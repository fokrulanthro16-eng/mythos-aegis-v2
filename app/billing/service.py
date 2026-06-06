"""BillingService — orchestrates provider calls and persists results.

Security invariants
-------------------
- No Stripe keys, secrets, or raw webhook payloads are ever logged.
- Webhook payload_json stores event type only — no financial data, no keys.
- Provider subscription IDs are stored as-is (they are not sensitive).
- tenant_id is always sourced from the validated SecurityContext.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import PLAN_FEATURES, PlanTier
from app.billing.providers.base import (
    AbstractBillingProvider,
    InvoiceInfo,
    SubscriptionInfo,
)
from app.billing.quota import QuotaEnforcer
from app.billing.schemas import (
    BillingEventResponse,
    CheckoutResponse,
    InvoiceResponse,
    QuotaStatusResponse,
    SubscriptionResponse,
)
from app.core.exceptions import BillingError, SubscriptionNotFoundError
from app.core.security_context import SecurityContext
from app.db.models.billing_event import BillingEvent
from app.db.models.billing_invoice import BillingInvoice
from app.db.models.billing_subscription import BillingSubscription
from app.observability.metrics import (
    billing_checkouts_total,
    billing_subscriptions_total,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


class BillingService:
    def __init__(
        self,
        session: AsyncSession,
        provider: AbstractBillingProvider,
    ) -> None:
        self._session = session
        self._provider = provider

    # ── Checkout ──────────────────────────────────────────────────────────────

    async def create_checkout(
        self,
        plan: PlanTier,
        success_url: str,
        cancel_url: str,
        ctx: SecurityContext,
    ) -> CheckoutResponse:
        checkout = await self._provider.create_checkout_session(
            tenant_id=ctx.tenant_id,
            plan=plan,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        billing_checkouts_total.labels(plan=plan.value).inc()
        logger.info(
            "billing.checkout.created tenant=%s plan=%s",
            ctx.tenant_id,
            plan,
        )
        return CheckoutResponse(
            session_id=checkout.session_id,
            checkout_url=checkout.checkout_url,
            plan=plan,
            expires_at=checkout.expires_at,
        )

    # ── Subscription ──────────────────────────────────────────────────────────

    async def activate_subscription(
        self,
        plan: PlanTier,
        session_id: str,
        ctx: SecurityContext,
    ) -> SubscriptionResponse:
        info = await self._provider.activate_subscription(
            tenant_id=ctx.tenant_id,
            plan=plan,
            session_id=session_id,
        )
        sub = await self._upsert_subscription(info, ctx.tenant_id)
        billing_subscriptions_total.labels(plan=plan.value, status="active").inc()
        logger.info(
            "billing.subscription.activated tenant=%s plan=%s",
            ctx.tenant_id,
            plan,
        )
        return self._to_subscription_response(sub)

    async def get_subscription(self, ctx: SecurityContext) -> SubscriptionResponse:
        sub = await self._fetch_active_subscription(ctx.tenant_id)
        return self._to_subscription_response(sub)

    async def cancel_subscription(self, ctx: SecurityContext) -> SubscriptionResponse:
        sub = await self._fetch_active_subscription(ctx.tenant_id)
        if not sub.provider_subscription_id:
            raise BillingError("No active provider subscription to cancel")

        info = await self._provider.cancel_subscription(sub.provider_subscription_id)
        sub.status = info.status
        sub.cancel_at_period_end = info.cancel_at_period_end
        self._session.add(sub)
        await self._session.flush()

        billing_subscriptions_total.labels(plan=sub.plan, status="cancelled").inc()
        logger.info("billing.subscription.cancelled tenant=%s", ctx.tenant_id)
        return self._to_subscription_response(sub)

    # ── Invoices ──────────────────────────────────────────────────────────────

    async def generate_invoice(self, ctx: SecurityContext) -> InvoiceResponse:
        sub = await self._fetch_active_subscription(ctx.tenant_id)
        if not sub.provider_subscription_id:
            raise BillingError("No active provider subscription for invoice generation")

        try:
            plan = PlanTier(sub.plan)
        except ValueError:
            plan = PlanTier.FREE
        amount_cents = PLAN_FEATURES[plan].price_monthly_cents

        info = await self._provider.generate_invoice(
            sub.provider_subscription_id, amount_cents
        )
        inv = await self._persist_invoice(info, sub.id, ctx.tenant_id)
        return self._to_invoice_response(inv)

    async def list_invoices(self, ctx: SecurityContext) -> list[InvoiceResponse]:
        result = await self._session.execute(
            select(BillingInvoice)
            .where(BillingInvoice.tenant_id == ctx.tenant_id)
            .order_by(BillingInvoice.invoice_date.desc())
            .limit(50)
        )
        return [self._to_invoice_response(inv) for inv in result.scalars().all()]

    # ── Webhooks ──────────────────────────────────────────────────────────────

    async def handle_webhook(
        self,
        payload: bytes,
        signature: str,
        fallback_tenant_id: UUID | None = None,
    ) -> BillingEventResponse:
        event = await self._provider.handle_webhook(payload, signature)
        tenant_id = event.tenant_id or fallback_tenant_id or UUID(int=0)

        billing_ev = BillingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            event_type=event.event_type,
            provider_event_id=event.event_id,
            payload_json=json.dumps({"type": event.event_type}),  # no secrets logged
            processed=True,
            created_at=_now(),
        )
        self._session.add(billing_ev)
        await self._session.flush()
        logger.info(
            "billing.webhook.processed type=%s event=%s",
            event.event_type,
            event.event_id,
        )
        return BillingEventResponse(
            event_id=billing_ev.id,
            event_type=event.event_type,
            processed=True,
            created_at=billing_ev.created_at,
        )

    # ── Quota ─────────────────────────────────────────────────────────────────

    async def get_quota_status(self, ctx: SecurityContext) -> QuotaStatusResponse:
        enforcer = QuotaEnforcer(self._session)
        status: dict[str, Any] = await enforcer.get_quota_status(ctx.tenant_id)
        return QuotaStatusResponse.model_validate(status)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _fetch_active_subscription(self, tenant_id: UUID) -> BillingSubscription:
        result = await self._session.execute(
            select(BillingSubscription)
            .where(
                BillingSubscription.tenant_id == tenant_id,
                BillingSubscription.status.in_(["active", "trialing", "past_due"]),
            )
            .order_by(BillingSubscription.created_at.desc())
            .limit(1)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            raise SubscriptionNotFoundError(
                f"No active subscription found for tenant {tenant_id}"
            )
        return sub

    async def _upsert_subscription(
        self, info: SubscriptionInfo, tenant_id: UUID
    ) -> BillingSubscription:
        result = await self._session.execute(
            select(BillingSubscription)
            .where(BillingSubscription.tenant_id == tenant_id)
            .order_by(BillingSubscription.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.plan = info.plan.value
            existing.status = info.status
            existing.provider_subscription_id = info.subscription_id
            existing.provider_customer_id = info.customer_id
            existing.current_period_start = info.current_period_start
            existing.current_period_end = info.current_period_end
            existing.cancel_at_period_end = info.cancel_at_period_end
            self._session.add(existing)
            await self._session.flush()
            return existing

        sub = BillingSubscription(
            id=uuid4(),
            tenant_id=tenant_id,
            plan=info.plan.value,
            status=info.status,
            provider_subscription_id=info.subscription_id,
            provider_customer_id=info.customer_id,
            current_period_start=info.current_period_start,
            current_period_end=info.current_period_end,
            cancel_at_period_end=info.cancel_at_period_end,
            created_at=_now(),
        )
        self._session.add(sub)
        await self._session.flush()
        return sub

    async def _persist_invoice(
        self, info: InvoiceInfo, sub_id: UUID, tenant_id: UUID
    ) -> BillingInvoice:
        inv = BillingInvoice(
            id=uuid4(),
            tenant_id=tenant_id,
            subscription_id=sub_id,
            provider_invoice_id=info.invoice_id,
            amount_cents=info.amount_cents,
            currency=info.currency,
            status=info.status,
            invoice_date=info.invoice_date,
            due_date=info.due_date,
            invoice_url=info.invoice_url,
            created_at=_now(),
        )
        self._session.add(inv)
        await self._session.flush()
        return inv

    @staticmethod
    def _to_subscription_response(sub: BillingSubscription) -> SubscriptionResponse:
        return SubscriptionResponse(
            subscription_id=sub.id,
            tenant_id=sub.tenant_id,
            plan=sub.plan,
            status=sub.status,
            provider_subscription_id=sub.provider_subscription_id,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=sub.cancel_at_period_end,
            created_at=sub.created_at,
        )

    @staticmethod
    def _to_invoice_response(inv: BillingInvoice) -> InvoiceResponse:
        return InvoiceResponse(
            invoice_id=inv.id,
            subscription_id=inv.subscription_id,
            amount_cents=inv.amount_cents,
            currency=inv.currency,
            status=inv.status,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
            invoice_url=inv.invoice_url,
            created_at=inv.created_at,
        )
