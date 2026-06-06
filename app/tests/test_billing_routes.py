"""HTTP-layer tests for the billing router."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.billing.models import PlanTier
from app.billing.schemas import (
    ApiRequestQuota,
    BillingEventResponse,
    CheckoutResponse,
    FeatureAccess,
    InvoiceResponse,
    PlanLimits,
    QuotaStatusResponse,
    SubscriptionResponse,
)
from app.core.security_context import SecurityContext


def _ctx(permissions: frozenset[str] | None = None) -> SecurityContext:
    if permissions is None:
        permissions = frozenset({"billing.manage", "billing.read", "billing.admin"})
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"admin"}),
        permissions=permissions,
    )


def _make_client(ctx: SecurityContext) -> Generator[TestClient, None, None]:
    from app.auth.dependencies import get_security_context
    from app.db.session import get_session
    from app.main import app

    app.dependency_overrides[get_security_context] = lambda: ctx
    app.dependency_overrides[get_session] = lambda: AsyncMock()

    with (
        patch("app.auth.middleware.validate_token", return_value={}),
        patch("app.auth.middleware.build_security_context", return_value=ctx),
    ):
        yield TestClient(
            app,
            raise_server_exceptions=False,
            headers={"Authorization": "Bearer test-token"},
        )

    app.dependency_overrides.clear()


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _sub_response(tenant_id: object = None) -> SubscriptionResponse:
    return SubscriptionResponse(
        subscription_id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        plan="pro",
        status="active",
        provider_subscription_id="mock_sub_abc",
        current_period_start=_now(),
        current_period_end=_now(),
        cancel_at_period_end=False,
        created_at=_now(),
    )


def _checkout_response() -> CheckoutResponse:
    return CheckoutResponse(
        session_id="mock_cs_abc",
        checkout_url="http://localhost/checkout",
        plan=PlanTier.PRO,
        expires_at=_now(),
    )


def _invoice_response() -> InvoiceResponse:
    return InvoiceResponse(
        invoice_id=uuid4(),
        subscription_id=uuid4(),
        amount_cents=4_900,
        currency="usd",
        status="paid",
        invoice_date=_now(),
        due_date=None,
        invoice_url="http://localhost/invoice",
        created_at=_now(),
    )


def _quota_response() -> QuotaStatusResponse:
    return QuotaStatusResponse(
        plan="pro",
        monthly_api_requests=ApiRequestQuota(used=100, limit=50_000, unlimited=False),
        features=FeatureAccess(rag_search=True, vision=True, workflow=True),
        limits=PlanLimits(
            max_projects=10, max_documents=10_000, max_workflow_executions=500
        ),
    )


# ── GET /v1/billing/plans ────────────────────────────────────────────────────


class TestListPlans:
    def test_returns_all_four_plans(self) -> None:
        ctx = _ctx()
        for client in _make_client(ctx):
            resp = client.get("/v1/billing/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        tiers = {p["tier"] for p in data}
        assert tiers == {"free", "pro", "business", "enterprise"}

    def test_free_plan_has_zero_price(self) -> None:
        ctx = _ctx()
        for client in _make_client(ctx):
            resp = client.get("/v1/billing/plans")
        free = next(p for p in resp.json() if p["tier"] == "free")
        assert free["price_monthly_cents"] == 0

    def test_no_auth_required_for_plans(self) -> None:
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/billing/plans")
        assert resp.status_code == 200


# ── POST /v1/billing/checkout ─────────────────────────────────────────────────


class TestCreateCheckout:
    def test_returns_201_with_checkout_url(self) -> None:
        ctx = _ctx()
        mock_svc = MagicMock()
        mock_svc.create_checkout = AsyncMock(return_value=_checkout_response())

        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.post(
                    "/v1/billing/checkout",
                    json={"plan": "pro"},
                )
        assert resp.status_code == 201
        assert resp.json()["session_id"] == "mock_cs_abc"

    def test_returns_403_without_permission(self) -> None:
        ctx = _ctx(permissions=frozenset({"billing.read"}))
        for client in _make_client(ctx):
            resp = client.post("/v1/billing/checkout", json={"plan": "pro"})
        assert resp.status_code == 403

    def test_invalid_plan_returns_422(self) -> None:
        ctx = _ctx()
        for client in _make_client(ctx):
            resp = client.post("/v1/billing/checkout", json={"plan": "invalid_plan"})
        assert resp.status_code == 422


# ── POST /v1/billing/checkout/activate ───────────────────────────────────────


class TestActivateSubscription:
    def test_returns_200_with_subscription(self) -> None:
        ctx = _ctx()
        mock_svc = MagicMock()
        mock_svc.activate_subscription = AsyncMock(return_value=_sub_response())

        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.post(
                    "/v1/billing/checkout/activate",
                    json={"plan": "pro", "session_id": "mock_cs_abc"},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_returns_403_without_permission(self) -> None:
        ctx = _ctx(permissions=frozenset({"billing.read"}))
        for client in _make_client(ctx):
            resp = client.post(
                "/v1/billing/checkout/activate",
                json={"plan": "pro", "session_id": "abc"},
            )
        assert resp.status_code == 403


# ── GET /v1/billing/subscription ─────────────────────────────────────────────


class TestGetSubscription:
    def test_returns_200_with_active_subscription(self) -> None:
        ctx = _ctx()
        mock_svc = MagicMock()
        mock_svc.get_subscription = AsyncMock(return_value=_sub_response())

        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.get("/v1/billing/subscription")
        assert resp.status_code == 200
        assert resp.json()["plan"] == "pro"

    def test_returns_404_when_no_subscription(self) -> None:
        from app.core.exceptions import SubscriptionNotFoundError

        ctx = _ctx()
        mock_svc = MagicMock()
        mock_svc.get_subscription = AsyncMock(
            side_effect=SubscriptionNotFoundError("no subscription")
        )
        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.get("/v1/billing/subscription")
        assert resp.status_code == 404

    def test_returns_403_without_permission(self) -> None:
        ctx = _ctx(permissions=frozenset({"billing.manage"}))
        for client in _make_client(ctx):
            resp = client.get("/v1/billing/subscription")
        assert resp.status_code == 403


# ── DELETE /v1/billing/subscription ──────────────────────────────────────────


class TestCancelSubscription:
    def test_returns_200_after_cancellation(self) -> None:
        ctx = _ctx()
        cancelled = _sub_response()
        cancelled.status = "cancelled"

        mock_svc = MagicMock()
        mock_svc.cancel_subscription = AsyncMock(return_value=cancelled)

        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.delete("/v1/billing/subscription")
        assert resp.status_code == 200

    def test_returns_403_without_permission(self) -> None:
        ctx = _ctx(permissions=frozenset({"billing.read"}))
        for client in _make_client(ctx):
            resp = client.delete("/v1/billing/subscription")
        assert resp.status_code == 403


# ── POST /v1/billing/invoices/generate ───────────────────────────────────────


class TestGenerateInvoice:
    def test_returns_200_with_invoice(self) -> None:
        ctx = _ctx()
        mock_svc = MagicMock()
        mock_svc.generate_invoice = AsyncMock(return_value=_invoice_response())

        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.post("/v1/billing/invoices/generate")
        assert resp.status_code == 200
        assert resp.json()["amount_cents"] == 4_900

    def test_returns_403_without_permission(self) -> None:
        ctx = _ctx(permissions=frozenset({"billing.read"}))
        for client in _make_client(ctx):
            resp = client.post("/v1/billing/invoices/generate")
        assert resp.status_code == 403


# ── GET /v1/billing/invoices ──────────────────────────────────────────────────


class TestListInvoices:
    def test_returns_200_with_invoice_list(self) -> None:
        ctx = _ctx()
        mock_svc = MagicMock()
        mock_svc.list_invoices = AsyncMock(return_value=[_invoice_response()])

        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.get("/v1/billing/invoices")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_returns_403_without_permission(self) -> None:
        ctx = _ctx(permissions=frozenset({"billing.manage"}))
        for client in _make_client(ctx):
            resp = client.get("/v1/billing/invoices")
        assert resp.status_code == 403


# ── POST /v1/billing/webhooks ─────────────────────────────────────────────────


class TestReceiveWebhook:
    def test_valid_json_webhook_returns_200(self) -> None:
        import json

        ctx = _ctx()
        mock_svc = MagicMock()
        mock_svc.handle_webhook = AsyncMock(
            return_value=BillingEventResponse(
                event_id=uuid4(),
                event_type="invoice.paid",
                processed=True,
                created_at=_now(),
            )
        )
        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.post(
                    "/v1/billing/webhooks",
                    content=json.dumps({"type": "invoice.paid"}).encode(),
                    headers={"Content-Type": "application/json"},
                )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "invoice.paid"

    def test_billing_error_returns_400(self) -> None:
        from app.core.exceptions import BillingError

        ctx = _ctx()
        mock_svc = MagicMock()
        mock_svc.handle_webhook = AsyncMock(side_effect=BillingError("bad payload"))
        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.post(
                    "/v1/billing/webhooks",
                    content=b"not json",
                )
        assert resp.status_code == 400


# ── GET /v1/billing/quota ─────────────────────────────────────────────────────


class TestGetQuota:
    def test_returns_200_with_quota_status(self) -> None:
        ctx = _ctx()
        mock_svc = MagicMock()
        mock_svc.get_quota_status = AsyncMock(return_value=_quota_response())

        for client in _make_client(ctx):
            with patch("app.billing.routes._get_service", return_value=mock_svc):
                resp = client.get("/v1/billing/quota")
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"] == "pro"
        assert body["monthly_api_requests"]["limit"] == 50_000
        assert body["features"]["vision"] is True

    def test_returns_403_without_permission(self) -> None:
        ctx = _ctx(permissions=frozenset({"billing.manage"}))
        for client in _make_client(ctx):
            resp = client.get("/v1/billing/quota")
        assert resp.status_code == 403
