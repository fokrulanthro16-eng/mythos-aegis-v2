"""Tenant AI quota enforcement.

Reads ``usage_records`` to check whether a tenant has exhausted their monthly
AI call allowance.  Returns ``Success(None)`` when under quota, ``Failure``
when the limit is reached so the caller can return a safe HTTP 429.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AIQuotaExceededError
from app.core.result import Failure, Result, Success
from app.db.models.usage_record import UsageRecord

logger = logging.getLogger(__name__)


class QuotaService:
    """Check and enforce per-tenant monthly AI call quotas."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check(
        self,
        tenant_id: UUID,
        billing_period: str,
        *,
        project_id: UUID | None = None,
    ) -> Result[None]:
        """Return ``Success(None)`` if the tenant is within quota.

        Returns ``Failure`` (with ``AIQuotaExceededError``) if the monthly
        limit has been reached.  When ``AI_QUOTA_ENABLED=false`` the check is
        skipped and ``Success(None)`` is always returned.
        """
        if not settings.AI_QUOTA_ENABLED:
            return Success(None)

        record = await self._fetch(tenant_id, billing_period, project_id=project_id)
        if record is None:
            return Success(None)

        limit = settings.AI_MONTHLY_REQUEST_LIMIT
        if record.ai_call_count >= limit:
            logger.warning(
                "quota.exceeded tenant_id=%s period=%s count=%d limit=%d",
                tenant_id,
                billing_period,
                record.ai_call_count,
                limit,
            )
            return Failure(
                error=AIQuotaExceededError("quota_exceeded"),
                message=(
                    f"AI call quota exceeded for {billing_period}. "
                    f"Limit: {limit:,} calls/month."
                ),
            )
        return Success(None)

    async def _fetch(
        self,
        tenant_id: UUID,
        billing_period: str,
        *,
        project_id: UUID | None,
    ) -> UsageRecord | None:
        result = await self._session.execute(
            select(UsageRecord).where(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.billing_period == billing_period,
                UsageRecord.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()
