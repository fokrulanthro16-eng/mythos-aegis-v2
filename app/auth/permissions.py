"""RBAC permission model and enforcement.

Each ActionType (refined by Intent for RAG_VISION) maps to exactly one
required Permission string.  CLARIFICATION and NOOP require no permission.

The check_permission function returns a Failure rather than raising so that
the orchestrator can synthesize a safe ResponsePayload without any exception
routing.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.exceptions import AuthorizationError
from app.core.result import Failure
from app.core.security_context import SecurityContext
from app.intent.enums import ActionType, Intent
from app.intent.schemas import IntentParseResult


class Permission(StrEnum):
    ORDERS_CANCEL = "orders.cancel"
    ANALYTICS_READ = "analytics.read"
    POLICIES_READ = "policies.read"
    VISION_ANALYZE = "vision.analyze"


# Maps specific RAG intents to their required permission.
_RAG_INTENT_PERMISSION: dict[Intent, Permission] = {
    Intent.POLICY_SEARCH: Permission.POLICIES_READ,
    Intent.VISION_RECEIPT_VALIDATE: Permission.VISION_ANALYZE,
    Intent.VISION_DAMAGE_ANALYSIS: Permission.VISION_ANALYZE,
}

# Maps non-RAG action types to their required permission.
_ACTION_PERMISSION: dict[ActionType, Permission] = {
    ActionType.WRITE_MUTATION: Permission.ORDERS_CANCEL,
    ActionType.SQL_ANALYTICS: Permission.ANALYTICS_READ,
}


def required_permission(parse_result: IntentParseResult) -> Permission | None:
    """Return the Permission required for this parse result, or None if none."""
    action = parse_result.action_type
    if action in _ACTION_PERMISSION:
        return _ACTION_PERMISSION[action]
    if action == ActionType.RAG_VISION:
        return _RAG_INTENT_PERMISSION.get(parse_result.intent)
    # CLARIFICATION and NOOP require no permission.
    return None


def check_permission(
    ctx: SecurityContext,
    parse_result: IntentParseResult,
) -> Failure | None:
    """Return a Failure if ctx lacks the required permission, else None.

    The Failure carries an AuthorizationError so the synthesizer maps it
    to "This action is not authorized." — no permission detail is revealed.
    """
    perm = required_permission(parse_result)
    if perm is None:
        return None
    if perm not in ctx.permissions:
        error = AuthorizationError("Insufficient permissions for this operation")
        return Failure(error=error, message=error.message)
    return None
