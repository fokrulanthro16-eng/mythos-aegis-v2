"""RBAC policy tool — check or list permissions for the current user."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolResult
from app.core.security_context import SecurityContext

logger = logging.getLogger(__name__)

_NAME = "rbac_check"


class RBACPolicyTool(BaseTool):
    """Check whether the current user has a permission, or list all permissions."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=_NAME,
            description=(
                "Check if the current user has a specific permission, or list "
                "all permissions and roles. Use when asked 'can I do X?' or "
                "about access levels."
            ),
            parameters=[
                ToolParameter(
                    "permission",
                    "string",
                    "The permission to check (e.g. 'rag.search'). "
                    "Leave empty to list all.",
                    required=False,
                    default="",
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
        permission: str = str(params.get("permission", "")).strip()

        if permission:
            granted = permission in ctx.permissions
            logger.debug(
                "tool.rbac_check perm=%s granted=%s tenant=%s",
                permission,
                granted,
                ctx.tenant_id,
            )
            return ToolResult(
                success=True, data={"permission": permission, "granted": granted}
            )

        return ToolResult(
            success=True,
            data={
                "permissions": sorted(ctx.permissions),
                "roles": sorted(ctx.roles),
            },
        )
