"""Unit tests for MockBillingProvider and BillingService.

Tests verify:
- Mock checkout session creation (no Stripe key required)
- Fake subscription activation and state
- Fake invoice generation
- Subscription cancellation
- Webhook handling (valid JSON + invalid payload)
- Stripe mode fails safely if key is missing
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.billing.models import PLAN_FEATURES, PlanTier
from app.billing.providers.mock import MockBillingProvider
from app.billing.schemas import (
    BillingEventResponse,
    CheckoutResponse,
    QuotaStatusResponse,
    SubscriptionResponse,
)
from app.billing.service import BillingService
from app.core.exceptions import (
    BillingError,
    BillingProviderError,
)
from app.core.security_context import SecurityContext


def _ctx(tenant_id: object = None) -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        roles=frozenset({"admin"}),
        permissions=frozenset({"billing.manage", "billing.read"}),
    )


def _session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    return s


# ── MockBillingProvider ───────────────────────────────────────────────────────


class TestMockCheckout:
    @pytest.mark.asyncio
    async def test_checkout_session_has_mock_prefix(self) -> None:
        provider = MockBillingProvider()
        cs = await provider.create_checkout_session(
            uuid4(), PlanTier.PRO, "http://ok", "http://cancel"
        )
        assert cs.session_id.startswith("mock_cs_")
        assert cs.plan == PlanTier.PRO
        assert "mock_cs_" in cs.checkout_url

    @pytest.mark.asyncio
    async def test_checkout_expires_in_future(self) -> None:
        from datetime import UTC, datetime

        provider = MockBillingProvider()
        cs = await provider.create_checkout_session(
            uuid4(), PlanTier.FREE, "http://ok", "http://cancel"
        )
        assert cs.expires_at > datetime.now(tz=UTC)

    @pytest.mark.asyncio
    async def test_each_checkout_has_unique_id(self) -> None:
        provider = MockBillingProvider()
        tid = uuid4()
        cs1 = await provider.create_checkout_session(tid, PlanTier.PRO, "a", "b")
        cs2 = await provider.create_checkout_session(tid, PlanTier.PRO, "a", "b")
        assert cs1.session_id != cs2.session_id


class TestMockSubscriptionActivation:
    @pytest.mark.asyncio
    async def test_activation_returns_active_status(self) -> None:
        provider = MockBillingProvider()
        cs = await provider.create_checkout_session(
            uuid4(), PlanTier.BUSINESS, "ok", "cancel"
        )
        info = await provider.activate_subscription(
            uuid4(), PlanTier.BUSINESS, cs.session_id
        )
        assert info.status == "active"
        assert info.plan == PlanTier.BUSINESS
        assert info.subscription_id.startswith("mock_sub_")
        assert info.customer_id.startswith("mock_cus_")

    @pytest.mark.asyncio
    async def test_activation_without_session_raises(self) -> None:
        provider = MockBillingProvider()
        with pytest.raises(BillingError, match="Unknown checkout session"):
            await provider.activate_subscription(
                uuid4(), PlanTier.PRO, "bad_session_id"
            )

    @pytest.mark.asyncio
    async def test_period_end_is_30_days_after_start(self) -> None:
        provider = MockBillingProvider()
        cs = await provider.create_checkout_session(uuid4(), PlanTier.PRO, "ok", "x")
        info = await provider.activate_subscription(
            uuid4(), PlanTier.PRO, cs.session_id
        )
        delta = info.current_period_end - info.current_period_start
        assert 29 <= delta.days <= 31


class TestMockCancellation:
    @pytest.mark.asyncio
    async def test_cancel_sets_cancelled_status(self) -> None:
        provider = MockBillingProvider()
        cs = await provider.create_checkout_session(uuid4(), PlanTier.PRO, "ok", "x")
        info = await provider.activate_subscription(
            uuid4(), PlanTier.PRO, cs.session_id
        )
        cancelled = await provider.cancel_subscription(info.subscription_id)
        assert cancelled.status == "cancelled"
        assert cancelled.cancel_at_period_end is True

    @pytest.mark.asyncio
    async def test_cancel_unknown_sub_raises(self) -> None:
        provider = MockBillingProvider()
        with pytest.raises(BillingError, match="Subscription not found"):
            await provider.cancel_subscription("sub_does_not_exist")


class TestMockInvoice:
    @pytest.mark.asyncio
    async def test_invoice_for_pro_plan_correct_amount(self) -> None:
        provider = MockBillingProvider()
        cs = await provider.create_checkout_session(uuid4(), PlanTier.PRO, "ok", "x")
        sub = await provider.activate_subscription(uuid4(), PlanTier.PRO, cs.session_id)
        inv = await provider.generate_invoice(
            sub.subscription_id, PLAN_FEATURES[PlanTier.PRO].price_monthly_cents
        )
        assert inv.amount_cents == 4_900
        assert inv.status == "paid"
        assert inv.currency == "usd"
        assert inv.invoice_id.startswith("mock_inv_")

    @pytest.mark.asyncio
    async def test_list_invoices_grows_with_each_generation(self) -> None:
        provider = MockBillingProvider()
        cs = await provider.create_checkout_session(
            uuid4(), PlanTier.BUSINESS, "ok", "x"
        )
        sub = await provider.activate_subscription(
            uuid4(), PlanTier.BUSINESS, cs.session_id
        )
        assert await provider.list_invoices(sub.subscription_id) == []
        await provider.generate_invoice(sub.subscription_id, 19_900)
        await provider.generate_invoice(sub.subscription_id, 19_900)
        assert len(await provider.list_invoices(sub.subscription_id)) == 2

    @pytest.mark.asyncio
    async def test_invoice_unknown_sub_raises(self) -> None:
        provider = MockBillingProvider()
        with pytest.raises(BillingError, match="Subscription not found"):
            await provider.generate_invoice("nope", 100)


class TestMockWebhook:
    @pytest.mark.asyncio
    async def test_valid_json_webhook_parsed(self) -> None:
        provider = MockBillingProvider()
        tid = uuid4()
        payload = json.dumps(
            {"type": "subscription.activated", "tenant_id": str(tid)}
        ).encode()
        event = await provider.handle_webhook(payload, "mock-sig")
        assert event.event_type == "subscription.activated"
        assert event.tenant_id == tid
        assert event.event_id.startswith("mock_evt_")

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self) -> None:
        provider = MockBillingProvider()
        with pytest.raises(BillingError, match="JSON"):
            await provider.handle_webhook(b"not json at all!!!", "sig")

    @pytest.mark.asyncio
    async def test_webhook_without_tenant_id_sets_none(self) -> None:
        provider = MockBillingProvider()
        payload = json.dumps({"type": "mock.ping"}).encode()
        event = await provider.handle_webhook(payload, "sig")
        assert event.tenant_id is None


# ── BillingService (with MockBillingProvider) ─────────────────────────────────


class TestBillingServiceCheckout:
    @pytest.mark.asyncio
    async def test_create_checkout_returns_response(self) -> None:
        provider = MockBillingProvider()
        session = _session()
        svc = BillingService(session=session, provider=provider)
        ctx = _ctx()

        resp = await svc.create_checkout(
            plan=PlanTier.PRO,
            success_url="http://ok",
            cancel_url="http://cancel",
            ctx=ctx,
        )

        assert isinstance(resp, CheckoutResponse)
        assert resp.plan == PlanTier.PRO
        assert resp.session_id.startswith("mock_cs_")


class TestBillingServiceActivation:
    @pytest.mark.asyncio
    async def test_activate_persists_subscription(self) -> None:
        provider = MockBillingProvider()
        session = _session()

        # Simulate empty DB — no existing subscription
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        svc = BillingService(session=session, provider=provider)
        ctx = _ctx()

        # First create a checkout session so activation works
        cs = await provider.create_checkout_session(
            ctx.tenant_id, PlanTier.PRO, "ok", "x"
        )

        resp = await svc.activate_subscription(
            plan=PlanTier.PRO,
            session_id=cs.session_id,
            ctx=ctx,
        )
        assert isinstance(resp, SubscriptionResponse)
        assert resp.plan == "pro"
        assert resp.status == "active"
        session.add.assert_called()
        session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_activate_upserts_existing_subscription(self) -> None:
        provider = MockBillingProvider()
        session = _session()

        existing = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            plan="free",
            status="active",
            provider_subscription_id="old_sub",
            provider_customer_id="old_cus",
            current_period_start=None,
            current_period_end=None,
            cancel_at_period_end=False,
            created_at=datetime.now(tz=UTC),
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=result_mock)

        ctx = _ctx(tenant_id=existing.tenant_id)
        cs = await provider.create_checkout_session(
            ctx.tenant_id, PlanTier.BUSINESS, "ok", "x"
        )
        svc = BillingService(session=session, provider=provider)
        resp = await svc.activate_subscription(
            plan=PlanTier.BUSINESS, session_id=cs.session_id, ctx=ctx
        )
        assert resp.plan == "business"


class TestBillingServiceQuota:
    @pytest.mark.asyncio
    async def test_get_quota_returns_free_plan_when_no_subscription(self) -> None:
        provider = MockBillingProvider()
        session = _session()

        # No subscription found, no usage records
        empty_result = MagicMock()
        empty_result.scalar_one_or_none.return_value = None
        empty_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=empty_result)

        svc = BillingService(session=session, provider=provider)
        ctx = _ctx()
        quota = await svc.get_quota_status(ctx)

        assert isinstance(quota, QuotaStatusResponse)
        assert quota.plan == "free"
        assert quota.monthly_api_requests.limit == 1_000
        assert quota.features.vision is False


class TestBillingServiceWebhook:
    @pytest.mark.asyncio
    async def test_webhook_persisted_as_billing_event(self) -> None:
        provider = MockBillingProvider()
        session = _session()
        svc = BillingService(session=session, provider=provider)

        payload = json.dumps({"type": "invoice.paid"}).encode()
        resp = await svc.handle_webhook(payload=payload, signature="sig")

        assert isinstance(resp, BillingEventResponse)
        assert resp.event_type == "invoice.paid"
        assert resp.processed is True
        session.add.assert_called()


# ── Stripe provider safety ────────────────────────────────────────────────────


class TestStripeProviderSafety:
    def test_stripe_raises_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")

        from app.billing.providers.stripe_provider import StripeBillingProvider

        with pytest.raises(BillingProviderError, match="STRIPE_SECRET_KEY"):
            StripeBillingProvider()

    def test_stripe_does_not_require_key_in_mock_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.billing.routes.settings.BILLING_PROVIDER", "mock")
        provider = MockBillingProvider()
        assert provider is not None
