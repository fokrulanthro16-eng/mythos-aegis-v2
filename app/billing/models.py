"""Billing plan definitions and per-plan feature limits."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class PlanTier(StrEnum):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class PlanFeatures(BaseModel):
    monthly_api_requests: int  # -1 = unlimited
    max_projects: int  # -1 = unlimited
    max_documents: int  # -1 = unlimited
    max_workflow_executions: int  # -1 = unlimited
    rag_search_enabled: bool
    vision_enabled: bool
    workflow_enabled: bool
    support_tier: str  # community | email | priority | dedicated
    price_monthly_cents: int


PLAN_FEATURES: dict[PlanTier, PlanFeatures] = {
    PlanTier.FREE: PlanFeatures(
        monthly_api_requests=1_000,
        max_projects=1,
        max_documents=100,
        max_workflow_executions=10,
        rag_search_enabled=True,
        vision_enabled=False,
        workflow_enabled=False,
        support_tier="community",
        price_monthly_cents=0,
    ),
    PlanTier.PRO: PlanFeatures(
        monthly_api_requests=50_000,
        max_projects=10,
        max_documents=10_000,
        max_workflow_executions=500,
        rag_search_enabled=True,
        vision_enabled=True,
        workflow_enabled=True,
        support_tier="email",
        price_monthly_cents=4_900,
    ),
    PlanTier.BUSINESS: PlanFeatures(
        monthly_api_requests=500_000,
        max_projects=100,
        max_documents=500_000,
        max_workflow_executions=10_000,
        rag_search_enabled=True,
        vision_enabled=True,
        workflow_enabled=True,
        support_tier="priority",
        price_monthly_cents=19_900,
    ),
    PlanTier.ENTERPRISE: PlanFeatures(
        monthly_api_requests=-1,
        max_projects=-1,
        max_documents=-1,
        max_workflow_executions=-1,
        rag_search_enabled=True,
        vision_enabled=True,
        workflow_enabled=True,
        support_tier="dedicated",
        price_monthly_cents=99_900,
    ),
}
