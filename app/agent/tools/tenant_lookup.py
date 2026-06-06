"""Tenant lookup tool — fetch current tenant metadata."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolResult
from app.core.security_context import SecurityContext
from app.db.models.tenant import Tenant
from app.db.models.tenant_member import TenantMember

logger = logging.getLogger(__name__)

_NAME = "tenant_lookup"


class TenantLookupTool(BaseTool):
    """Return current tenant info (name, plan, status, member count)."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=_NAME,
            description=(
                "Look up information about the current tenant (organization). "
                "Returns name, subscription plan, status, and member count. "
                "Use when the user asks about their account or organization."
            ),
            parameters=[
                ToolParameter(
                    "include_members",
                    "boolean",
                    "Include member count (default true)",
                    required=False,
                    default=True,
                ),
            ],
            required_permission=None,
        )

    async def execute(
        self,
        params: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> ToolResult:
        include_members: bool = bool(params.get("include_members", True))

        result = await session.execute(
            select(Tenant).where(
                Tenant.id == ctx.tenant_id,
                Tenant.deleted_at.is_(None),
            )
        )
        tenant = result.scalar_one_or_none()
        if tenant is None:
            return ToolResult(success=False, data=None, error="Tenant not found")

        data: dict[str, Any] = {
            "name": tenant.name,
            "plan": tenant.plan,
            "status": tenant.status,
        }

        if include_members:
            count_res = await session.execute(
                select(func.count(TenantMember.id)).where(
                    TenantMember.tenant_id == ctx.tenant_id
                )
            )
            data["member_count"] = int(count_res.scalar() or 0)

        logger.debug("tool.tenant_lookup tenant=%s", ctx.tenant_id)
        return ToolResult(success=True, data=data)
