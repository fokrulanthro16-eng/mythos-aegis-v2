"""Billing REST API — plans, checkout, subscription, invoices, quota."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_security_context
from app.billing.models import PLAN_FEATURES
from app.billing.providers.mock import MockBillingProvider
from app.billing.schemas import (
    ActivateSubscriptionRequest,
    BillingEventResponse,
    CheckoutResponse,
    CreateCheckoutRequest,
    InvoiceResponse,
    PlanResponse,
    QuotaStatusResponse,
    SubscriptionResponse,
)
from app.billing.service import BillingService
from app.core.config import settings
from app.core.exceptions import (
    BillingError,
    BillingProviderError,
    SubscriptionNotFoundError,
)
from app.core.security_context import SecurityContext
from app.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/billing", tags=["billing"])

_SecurityCtx = Annotated[SecurityContext, Depends(get_security_context)]
_DbSession = Annotated[AsyncSession, Depends(get_session)]


def _get_provider() -> MockBillingProvider:  # return type widened in stripe branch
    if settings.BILLING_PROVIDER == "stripe":
        from app.billing.providers.stripe_provider import (
            StripeBillingProvider,  # noqa: PLC0415
        )

        return StripeBillingProvider()  # type: ignore[return-value]
    return MockBillingProvider()


def _get_service(session: AsyncSession) -> BillingService:
    return BillingService(session=session, provider=_get_provider())


# ── Public — no auth required ─────────────────────────────────────────────────


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans() -> list[PlanResponse]:
    return [
        PlanResponse(
            tier=tier,
            name=tier.value.title(),
            **features.model_dump(),
        )
        for tier, features in PLAN_FEATURES.items()
    ]


# ── Checkout ──────────────────────────────────────────────────────────────────


@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
async def create_checkout(
    req: CreateCheckoutRequest,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> CheckoutResponse:
    if "billing.manage" not in ctx.permissions:
        raise HTTPException(
            status_code=403, detail="billing.manage permission required"
        )
    svc = _get_service(session)
    try:
        return await svc.create_checkout(
            plan=req.plan,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            ctx=ctx,
        )
    except BillingProviderError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/checkout/activate", response_model=SubscriptionResponse)
async def activate_subscription(
    req: ActivateSubscriptionRequest,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> SubscriptionResponse:
    if "billing.manage" not in ctx.permissions:
        raise HTTPException(
            status_code=403, detail="billing.manage permission required"
        )
    svc = _get_service(session)
    try:
        return await svc.activate_subscription(
            plan=req.plan,
            session_id=req.session_id,
            ctx=ctx,
        )
    except BillingProviderError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


# ── Subscription ──────────────────────────────────────────────────────────────


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    ctx: _SecurityCtx,
    session: _DbSession,
) -> SubscriptionResponse:
    if "billing.read" not in ctx.permissions:
        raise HTTPException(status_code=403, detail="billing.read permission required")
    svc = _get_service(session)
    try:
        return await svc.get_subscription(ctx)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.delete("/subscription", response_model=SubscriptionResponse)
async def cancel_subscription(
    ctx: _SecurityCtx,
    session: _DbSession,
) -> SubscriptionResponse:
    if "billing.manage" not in ctx.permissions:
        raise HTTPException(
            status_code=403, detail="billing.manage permission required"
        )
    svc = _get_service(session)
    try:
        return await svc.cancel_subscription(ctx)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


# ── Invoices ──────────────────────────────────────────────────────────────────


@router.post("/invoices/generate", response_model=InvoiceResponse)
async def generate_invoice(
    ctx: _SecurityCtx,
    session: _DbSession,
) -> InvoiceResponse:
    if "billing.manage" not in ctx.permissions:
        raise HTTPException(
            status_code=403, detail="billing.manage permission required"
        )
    svc = _get_service(session)
    try:
        return await svc.generate_invoice(ctx)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    ctx: _SecurityCtx,
    session: _DbSession,
) -> list[InvoiceResponse]:
    if "billing.read" not in ctx.permissions:
        raise HTTPException(status_code=403, detail="billing.read permission required")
    svc = _get_service(session)
    return await svc.list_invoices(ctx)


# ── Webhooks — no JWT auth, provider signature is the security boundary ───────


@router.post("/webhooks", response_model=BillingEventResponse)
async def receive_webhook(
    request: Request,
    session: _DbSession,
) -> BillingEventResponse:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "mock-signature")
    svc = _get_service(session)
    try:
        return await svc.handle_webhook(payload=payload, signature=signature)
    except BillingProviderError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


# ── Quota ─────────────────────────────────────────────────────────────────────


@router.get("/quota", response_model=QuotaStatusResponse)
async def get_quota(
    ctx: _SecurityCtx,
    session: _DbSession,
) -> QuotaStatusResponse:
    if "billing.read" not in ctx.permissions:
        raise HTTPException(status_code=403, detail="billing.read permission required")
    svc = _get_service(session)
    return await svc.get_quota_status(ctx)
