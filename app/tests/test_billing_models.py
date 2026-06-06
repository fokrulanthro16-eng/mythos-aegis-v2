"""Unit tests for billing domain models, plan features, and provider DTOs."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.billing.models import PLAN_FEATURES, PlanFeatures, PlanTier
from app.billing.providers.base import (
    CheckoutSession,
    InvoiceInfo,
    SubscriptionInfo,
    WebhookEvent,
)

# ── PlanTier ─────────────────────────────────────────────────────────────────


class TestPlanTier:
    def test_all_tiers_exist(self) -> None:
        assert PlanTier.FREE.value == "free"
        assert PlanTier.PRO.value == "pro"
        assert PlanTier.BUSINESS.value == "business"
        assert PlanTier.ENTERPRISE.value == "enterprise"

    def test_from_string(self) -> None:
        assert PlanTier("pro") is PlanTier.PRO

    def test_invalid_tier_raises(self) -> None:
        with pytest.raises(ValueError):
            PlanTier("unknown")

    def test_str_equality(self) -> None:
        assert PlanTier.FREE.value == "free"
        assert PlanTier.PRO.value == "pro"


# ── PlanFeatures / PLAN_FEATURES ──────────────────────────────────────────────


class TestPlanFeatures:
    def test_all_four_plans_defined(self) -> None:
        assert len(PLAN_FEATURES) == 4
        assert PlanTier.FREE in PLAN_FEATURES
        assert PlanTier.PRO in PLAN_FEATURES
        assert PlanTier.BUSINESS in PLAN_FEATURES
        assert PlanTier.ENTERPRISE in PLAN_FEATURES

    def test_free_plan_is_cheapest(self) -> None:
        assert PLAN_FEATURES[PlanTier.FREE].price_monthly_cents == 0

    def test_price_ascending(self) -> None:
        prices = [PLAN_FEATURES[t].price_monthly_cents for t in PlanTier]
        assert prices == sorted(prices)

    def test_enterprise_is_unlimited(self) -> None:
        ent = PLAN_FEATURES[PlanTier.ENTERPRISE]
        assert ent.monthly_api_requests == -1
        assert ent.max_projects == -1
        assert ent.max_documents == -1
        assert ent.max_workflow_executions == -1

    def test_free_has_limited_features(self) -> None:
        free = PLAN_FEATURES[PlanTier.FREE]
        assert not free.vision_enabled
        assert not free.workflow_enabled
        assert free.rag_search_enabled

    def test_pro_enables_vision_and_workflow(self) -> None:
        pro = PLAN_FEATURES[PlanTier.PRO]
        assert pro.vision_enabled
        assert pro.workflow_enabled

    def test_business_higher_limits_than_pro(self) -> None:
        pro = PLAN_FEATURES[PlanTier.PRO]
        biz = PLAN_FEATURES[PlanTier.BUSINESS]
        assert biz.monthly_api_requests > pro.monthly_api_requests
        assert biz.max_projects > pro.max_projects

    def test_support_tiers(self) -> None:
        assert PLAN_FEATURES[PlanTier.FREE].support_tier == "community"
        assert PLAN_FEATURES[PlanTier.PRO].support_tier == "email"
        assert PLAN_FEATURES[PlanTier.BUSINESS].support_tier == "priority"
        assert PLAN_FEATURES[PlanTier.ENTERPRISE].support_tier == "dedicated"

    def test_plan_features_is_pydantic_model(self) -> None:
        features = PLAN_FEATURES[PlanTier.PRO]
        assert isinstance(features, PlanFeatures)
        d = features.model_dump()
        assert "monthly_api_requests" in d
        assert "vision_enabled" in d


# ── Provider DTOs ─────────────────────────────────────────────────────────────


class TestCheckoutSession:
    def test_create(self) -> None:
        cs = CheckoutSession(
            session_id="mock_cs_abc123",
            checkout_url="http://localhost/checkout",
            plan=PlanTier.PRO,
            tenant_id=uuid4(),
            expires_at=datetime.now(tz=UTC),
        )
        assert cs.session_id == "mock_cs_abc123"
        assert cs.plan == PlanTier.PRO


class TestSubscriptionInfo:
    def test_create(self) -> None:
        info = SubscriptionInfo(
            subscription_id="mock_sub_x",
            customer_id="mock_cus_y",
            plan=PlanTier.BUSINESS,
            status="active",
            current_period_start=datetime.now(tz=UTC),
            current_period_end=datetime.now(tz=UTC),
            cancel_at_period_end=False,
        )
        assert info.status == "active"
        assert info.plan == PlanTier.BUSINESS


class TestInvoiceInfo:
    def test_create(self) -> None:
        inv = InvoiceInfo(
            invoice_id="mock_inv_z",
            subscription_id="mock_sub_x",
            amount_cents=4_900,
            currency="usd",
            status="paid",
            invoice_date=datetime.now(tz=UTC),
            due_date=None,
            invoice_url=None,
        )
        assert inv.amount_cents == 4_900
        assert inv.status == "paid"


class TestWebhookEvent:
    def test_create_with_tenant(self) -> None:
        tid = uuid4()
        ev = WebhookEvent(
            event_id="mock_evt_1",
            event_type="subscription.activated",
            tenant_id=tid,
            timestamp=datetime.now(tz=UTC),
            data={"type": "subscription.activated"},
        )
        assert ev.tenant_id == tid
        assert ev.event_type == "subscription.activated"

    def test_create_without_tenant(self) -> None:
        ev = WebhookEvent(
            event_id="mock_evt_2",
            event_type="mock.ping",
            tenant_id=None,
            timestamp=datetime.now(tz=UTC),
            data={},
        )
        assert ev.tenant_id is None
