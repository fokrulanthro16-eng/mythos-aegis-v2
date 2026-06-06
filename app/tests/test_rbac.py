"""Tests for app/auth/permissions.py — RBAC permission enforcement."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.auth.permissions import Permission, check_permission, required_permission
from app.core.result import Failure
from app.core.security_context import SecurityContext
from app.intent.enums import ActionType, Intent
from app.intent.schemas import IntentParseResult
from app.orchestrator import route

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(intent: Intent, action_type: ActionType) -> IntentParseResult:
    return IntentParseResult(
        intent=intent,
        confidence=0.95,
        entities={},
        action_type=action_type,
        raw_text_hash="sha256-rbac-test",
    )


def _ctx(*, permissions: frozenset[str] = frozenset()) -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=permissions,
    )


_ALL = frozenset({"orders.cancel", "analytics.read", "policies.read", "vision.analyze"})


# ---------------------------------------------------------------------------
# Permission enum values
# ---------------------------------------------------------------------------


def test_permission_enum_values() -> None:
    assert Permission.ORDERS_CANCEL.value == "orders.cancel"
    assert Permission.ANALYTICS_READ.value == "analytics.read"
    assert Permission.POLICIES_READ.value == "policies.read"
    assert Permission.VISION_ANALYZE.value == "vision.analyze"


# ---------------------------------------------------------------------------
# required_permission — action-type mapping
# ---------------------------------------------------------------------------


def test_write_mutation_requires_orders_cancel() -> None:
    parse_result = _parse(Intent.CANCEL_ORDER, ActionType.WRITE_MUTATION)
    assert required_permission(parse_result) == Permission.ORDERS_CANCEL


def test_sql_analytics_requires_analytics_read() -> None:
    parse_result = _parse(Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS)
    assert required_permission(parse_result) == Permission.ANALYTICS_READ


def test_policy_search_requires_policies_read() -> None:
    parse_result = _parse(Intent.POLICY_SEARCH, ActionType.RAG_VISION)
    assert required_permission(parse_result) == Permission.POLICIES_READ


def test_vision_receipt_requires_vision_analyze() -> None:
    parse_result = _parse(Intent.VISION_RECEIPT_VALIDATE, ActionType.RAG_VISION)
    assert required_permission(parse_result) == Permission.VISION_ANALYZE


def test_vision_damage_requires_vision_analyze() -> None:
    parse_result = _parse(Intent.VISION_DAMAGE_ANALYSIS, ActionType.RAG_VISION)
    assert required_permission(parse_result) == Permission.VISION_ANALYZE


def test_clarification_requires_no_permission() -> None:
    parse_result = _parse(Intent.CLARIFY, ActionType.CLARIFICATION)
    assert required_permission(parse_result) is None


def test_noop_requires_no_permission() -> None:
    parse_result = _parse(Intent.UNKNOWN, ActionType.NOOP)
    assert required_permission(parse_result) is None


# ---------------------------------------------------------------------------
# check_permission — allows when permission is present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intent,action_type,permission",
    [
        (Intent.CANCEL_ORDER, ActionType.WRITE_MUTATION, "orders.cancel"),
        (Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS, "analytics.read"),
        (Intent.POLICY_SEARCH, ActionType.RAG_VISION, "policies.read"),
        (Intent.VISION_RECEIPT_VALIDATE, ActionType.RAG_VISION, "vision.analyze"),
    ],
)
def test_check_permission_allows_when_granted(
    intent: Intent, action_type: ActionType, permission: str
) -> None:
    parse_result = _parse(intent, action_type)
    ctx = _ctx(permissions=frozenset({permission}))
    result = check_permission(ctx, parse_result)
    assert result is None


# ---------------------------------------------------------------------------
# check_permission — blocks when permission is absent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intent,action_type",
    [
        (Intent.CANCEL_ORDER, ActionType.WRITE_MUTATION),
        (Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS),
        (Intent.POLICY_SEARCH, ActionType.RAG_VISION),
        (Intent.VISION_RECEIPT_VALIDATE, ActionType.RAG_VISION),
    ],
)
def test_check_permission_blocks_when_missing(
    intent: Intent, action_type: ActionType
) -> None:
    parse_result = _parse(intent, action_type)
    ctx = _ctx(permissions=frozenset())
    result = check_permission(ctx, parse_result)
    assert isinstance(result, Failure)


def test_check_permission_no_permission_needed_returns_none() -> None:
    parse_result = _parse(Intent.CLARIFY, ActionType.CLARIFICATION)
    ctx = _ctx(permissions=frozenset())
    result = check_permission(ctx, parse_result)
    assert result is None


# ---------------------------------------------------------------------------
# Orchestrator integration — RBAC enforced in route()
# ---------------------------------------------------------------------------


async def test_orchestrator_blocks_missing_permission() -> None:
    parse_result = _parse(Intent.CANCEL_ORDER, ActionType.WRITE_MUTATION)
    ctx = _ctx(permissions=frozenset())  # no orders.cancel
    payload = await route(parse_result, ctx)
    # Authorization failure → safe payload with a warning
    assert len(payload.warnings) > 0 or "not authorized" in payload.summary.lower()


async def test_orchestrator_allows_correct_permission() -> None:
    parse_result = _parse(Intent.CLARIFY, ActionType.CLARIFICATION)
    ctx = _ctx(permissions=frozenset())  # CLARIFICATION needs no permission
    payload = await route(parse_result, ctx)
    # Clarification path returns a question-style summary
    assert len(payload.summary) > 0
