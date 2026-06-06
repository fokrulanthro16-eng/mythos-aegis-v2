"""API-layer request and response schemas for the billing module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.billing.models import PlanTier

# ── Requests ──────────────────────────────────────────────────────────────────


class CreateCheckoutRequest(BaseModel):
    plan: PlanTier
    success_url: str = Field(default="http://localhost:8000/billing/success")
    cancel_url: str = Field(default="http://localhost:8000/billing/cancel")


class ActivateSubscriptionRequest(BaseModel):
    plan: PlanTier
    session_id: str = Field(min_length=1)


# ── Responses ─────────────────────────────────────────────────────────────────


class CheckoutResponse(BaseModel):
    session_id: str
    checkout_url: str
    plan: PlanTier
    expires_at: datetime


class SubscriptionResponse(BaseModel):
    subscription_id: UUID
    tenant_id: UUID
    plan: str
    status: str
    provider_subscription_id: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    created_at: datetime


class InvoiceResponse(BaseModel):
    invoice_id: UUID
    subscription_id: UUID
    amount_cents: int
    currency: str
    status: str
    invoice_date: datetime
    due_date: datetime | None
    invoice_url: str | None
    created_at: datetime


class BillingEventResponse(BaseModel):
    event_id: UUID
    event_type: str
    processed: bool
    created_at: datetime


class PlanResponse(BaseModel):
    tier: PlanTier
    name: str
    monthly_api_requests: int
    max_projects: int
    max_documents: int
    max_workflow_executions: int
    rag_search_enabled: bool
    vision_enabled: bool
    workflow_enabled: bool
    support_tier: str
    price_monthly_cents: int


# ── Nested quota schemas ───────────────────────────────────────────────────────


class ApiRequestQuota(BaseModel):
    used: int
    limit: int  # -1 = unlimited
    unlimited: bool


class FeatureAccess(BaseModel):
    rag_search: bool
    vision: bool
    workflow: bool


class PlanLimits(BaseModel):
    max_projects: int
    max_documents: int
    max_workflow_executions: int


class QuotaStatusResponse(BaseModel):
    plan: str
    monthly_api_requests: ApiRequestQuota
    features: FeatureAccess
    limits: PlanLimits
