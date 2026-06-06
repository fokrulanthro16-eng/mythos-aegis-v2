"""Quota enforcement — checks per-tenant plan limits before allowing operations.

Usage counts are read from UsageRecord (billing_period = YYYY-MM).
Plan tier is read from BillingSubscription; tenants with no active subscription
default to the FREE plan.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import PLAN_FEATURES, PlanTier
from app.core.exceptions import QuotaExceededError
from app.db.models.billing_subscription import BillingSubscription
from app.db.models.usage_record import UsageRecord

logger = logging.getLogger(__name__)


def _current_billing_period() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m")


class QuotaEnforcer:
    """Check and enforce per-tenant plan limits."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_plan(self, tenant_id: UUID) -> PlanTier:
        result = await self._session.execute(
            select(BillingSubscription)
            .where(
                BillingSubscription.tenant_id == tenant_id,
                BillingSubscription.status == "active",
            )
            .order_by(BillingSubscription.created_at.desc())
            .limit(1)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            return PlanTier.FREE
        try:
            return PlanTier(sub.plan)
        except ValueError:
            return PlanTier.FREE

    async def _get_monthly_requests(self, tenant_id: UUID) -> int:
        period = _current_billing_period()
        result = await self._session.execute(
            select(UsageRecord).where(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.billing_period == period,
            )
        )
        return sum(r.request_count for r in result.scalars().all())

    async def check_api_request(self, tenant_id: UUID) -> None:
        """Raise QuotaExceededError if monthly API request limit is reached."""
        plan = await self._get_plan(tenant_id)
        features = PLAN_FEATURES[plan]

        if features.monthly_api_requests == -1:
            return  # unlimited

        usage = await self._get_monthly_requests(tenant_id)
        if usage >= features.monthly_api_requests:
            raise QuotaExceededError(
                f"Monthly API request limit of {features.monthly_api_requests:,} "
                f"reached on the {plan.value} plan. Upgrade to continue."
            )
        logger.debug(
            "quota.api_request.ok tenant=%s used=%d limit=%d",
            tenant_id,
            usage,
            features.monthly_api_requests,
        )

    async def check_feature(self, tenant_id: UUID, feature: str) -> None:
        """Raise QuotaExceededError if feature is not available on current plan."""
        plan = await self._get_plan(tenant_id)
        features = PLAN_FEATURES[plan]

        feature_map: dict[str, bool] = {
            "vision": features.vision_enabled,
            "workflow": features.workflow_enabled,
            "rag_search": features.rag_search_enabled,
        }

        enabled = feature_map.get(feature)
        if enabled is None:
            logger.warning("quota.unknown_feature feature=%s", feature)
            return  # unknown features are not blocked

        if not enabled:
            raise QuotaExceededError(
                f"Feature '{feature}' is not available on the {plan.value} plan. "
                "Upgrade your plan to access this feature."
            )

    async def check_project_limit(self, tenant_id: UUID, current_count: int) -> None:
        """Raise QuotaExceededError if tenant has reached the project limit."""
        plan = await self._get_plan(tenant_id)
        features = PLAN_FEATURES[plan]

        if features.max_projects == -1:
            return

        if current_count >= features.max_projects:
            raise QuotaExceededError(
                f"Project limit of {features.max_projects} reached on the "
                f"{plan.value} plan. Upgrade to create more projects."
            )

    async def get_quota_status(self, tenant_id: UUID) -> dict[str, Any]:
        """Return current quota status dict for a tenant."""
        plan = await self._get_plan(tenant_id)
        features = PLAN_FEATURES[plan]
        monthly_requests = await self._get_monthly_requests(tenant_id)

        return {
            "plan": plan.value,
            "monthly_api_requests": {
                "used": monthly_requests,
                "limit": features.monthly_api_requests,
                "unlimited": features.monthly_api_requests == -1,
            },
            "features": {
                "rag_search": features.rag_search_enabled,
                "vision": features.vision_enabled,
                "workflow": features.workflow_enabled,
            },
            "limits": {
                "max_projects": features.max_projects,
                "max_documents": features.max_documents,
                "max_workflow_executions": features.max_workflow_executions,
            },
        }
