"""Audit log tool — write a compliance audit event on behalf of the agent."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolResult
from app.core.security_context import SecurityContext
from app.db.models.audit_event import ActorType, AuditEvent, AuditOutcome

logger = logging.getLogger(__name__)

_NAME = "audit_log"


class AuditLogTool(BaseTool):
    """Write a sanitized compliance audit event.

    The details field must not contain secrets, tokens, or personal data —
    the tool enforces no technical guardrail but the security contract applies.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=_NAME,
            description=(
                "Write a compliance audit event. Use when a significant action "
                "should be recorded for audit purposes (e.g. document accessed, "
                "report exported)."
            ),
            parameters=[
                ToolParameter(
                    "action",
                    "string",
                    "Action being logged (e.g. 'document.accessed'). Max 100 chars.",
                    required=True,
                ),
                ToolParameter(
                    "resource_type",
                    "string",
                    "Resource type acted on (e.g. 'document', 'report').",
                    required=False,
                    default="",
                ),
                ToolParameter(
                    "details",
                    "string",
                    "Sanitized context. Must not contain secrets or tokens.",
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
        action: str = str(params.get("action", "")).strip()[:100]
        resource_type: str = str(params.get("resource_type", "")).strip()[:80]
        details: str = str(params.get("details", "")).strip()

        if not action:
            return ToolResult(success=False, data=None, error="action is required")

        event_id = uuid4()
        event = AuditEvent(
            id=event_id,
            tenant_id=ctx.tenant_id,
            actor_id=ctx.current_user_id,
            actor_type=ActorType.USER,
            action=action,
            resource_type=resource_type or None,
            outcome=AuditOutcome.SUCCESS,
            extra_json=details or None,
        )
        session.add(event)
        await session.flush()

        logger.info(
            "tool.audit_log event_id=%s action=%s tenant=%s",
            event_id,
            action,
            ctx.tenant_id,
        )
        return ToolResult(
            success=True, data={"event_id": str(event_id), "action": action}
        )
