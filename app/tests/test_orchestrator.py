"""Tests for app/orchestrator.py — routing and global exception boundary.

Uses unittest.mock.patch to isolate the pathway services so only the
routing logic and exception boundary are exercised.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import MythosError
from app.core.result import Success
from app.core.security_context import SecurityContext
from app.intent.enums import ActionType, Intent
from app.intent.schemas import IntentParseResult
from app.orchestrator import route
from app.pathways.rag_vision.interfaces import MockPolicySearchProvider
from app.pathways.rag_vision.schemas import PolicySearchResult, PolicySummary
from app.pathways.sql_airlock.schemas import AnalyticsResponse
from app.pathways.write.mfa import MockMFAProvider
from app.pathways.write.schemas import CancelOrderResponse
from app.response.schemas import ResponsePayload

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ctx(*, request_id: UUID | None = None) -> SecurityContext:
    return SecurityContext(
        request_id=request_id or uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=frozenset(
            {"orders.cancel", "analytics.read", "policies.read", "vision.analyze"}
        ),
    )


def _parse(intent: Intent, action_type: ActionType) -> IntentParseResult:
    return IntentParseResult(
        intent=intent,
        confidence=0.95,
        entities={},
        action_type=action_type,
        raw_text_hash="sha256-test",
    )


# ---------------------------------------------------------------------------
# NOOP → Failure → safe ResponsePayload
# ---------------------------------------------------------------------------


async def test_noop_returns_safe_payload() -> None:
    parse_result = IntentParseResult(
        intent=Intent.UNKNOWN,
        confidence=0.95,
        entities={},
        action_type=ActionType.NOOP,
        raw_text_hash="hash",
    )
    ctx = _ctx()
    payload = await route(parse_result, ctx)

    assert isinstance(payload, ResponsePayload)
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# CLARIFICATION → execute_clarification (pure, no mocks needed)
# ---------------------------------------------------------------------------


async def test_clarification_routing_returns_question() -> None:
    parse_result = IntentParseResult(
        intent=Intent.CLARIFY,
        confidence=0.40,
        entities={},
        action_type=ActionType.CLARIFICATION,
        raw_text_hash="sha256-clarify",
    )
    ctx = _ctx()
    payload = await route(parse_result, ctx)

    assert isinstance(payload, ResponsePayload)
    assert len(payload.summary) > 0
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# WRITE_MUTATION routing
# ---------------------------------------------------------------------------


async def test_write_routing_without_session_returns_failure_payload() -> None:
    parse_result = _parse(Intent.CANCEL_ORDER, ActionType.WRITE_MUTATION)
    ctx = _ctx()
    payload = await route(parse_result, ctx, session=None)

    assert isinstance(payload, ResponsePayload)
    assert payload.request_id == str(ctx.request_id)


async def test_write_routing_calls_execute_cancel_order() -> None:
    mock_session = AsyncMock()
    ts = datetime(2024, 6, 1, tzinfo=UTC)
    order_id = uuid4()
    mock_response = Success(
        value=CancelOrderResponse(
            operation_status="cancelled",
            order_id=order_id,
            cancelled_at=ts,
        )
    )
    parse_result = IntentParseResult(
        intent=Intent.CANCEL_ORDER,
        confidence=0.95,
        entities={"order_id": str(order_id)},
        action_type=ActionType.WRITE_MUTATION,
        raw_text_hash="hash",
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_cancel_order",
        AsyncMock(return_value=mock_response),
    ):
        payload = await route(
            parse_result, ctx, session=mock_session, mfa_provider=MockMFAProvider()
        )

    assert str(order_id) in payload.summary
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# SQL_ANALYTICS routing
# ---------------------------------------------------------------------------


async def test_sql_routing_without_session_returns_failure_payload() -> None:
    parse_result = _parse(Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS)
    ctx = _ctx()
    payload = await route(parse_result, ctx, session=None)

    assert isinstance(payload, ResponsePayload)
    assert payload.request_id == str(ctx.request_id)


async def test_sql_routing_calls_analytics_service() -> None:
    mock_session = AsyncMock()
    rows: list[dict[str, object]] = [{"id": "1", "status": "pending"}]
    mock_response = Success(value=AnalyticsResponse(rows=rows, row_count=1))
    parse_result = IntentParseResult(
        intent=Intent.ANALYTICS_QUERY,
        confidence=0.95,
        entities={"sql": "SELECT id, status FROM orders"},
        action_type=ActionType.SQL_ANALYTICS,
        raw_text_hash="hash",
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_analytics_query",
        AsyncMock(return_value=mock_response),
    ):
        payload = await route(parse_result, ctx, session=mock_session)

    assert "1 row" in payload.summary
    assert payload.markdown_table is not None


# ---------------------------------------------------------------------------
# RAG_VISION routing
# ---------------------------------------------------------------------------


async def test_rag_policy_routing_with_provider() -> None:
    mock_response = Success(
        value=PolicySearchResult(
            policies=[
                PolicySummary(
                    title="Test Policy",
                    excerpt="An excerpt.",
                    relevance=0.85,
                )
            ],
            result_count=1,
        )
    )
    parse_result = IntentParseResult(
        intent=Intent.POLICY_SEARCH,
        confidence=0.95,
        entities={"query": "collision coverage"},
        action_type=ActionType.RAG_VISION,
        raw_text_hash="hash",
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.search_policies",
        AsyncMock(return_value=mock_response),
    ):
        payload = await route(
            parse_result, ctx, policy_provider=MockPolicySearchProvider()
        )

    assert "Test Policy" in payload.summary
    assert payload.request_id == str(ctx.request_id)


async def test_rag_routing_without_provider_returns_failure_payload() -> None:
    parse_result = IntentParseResult(
        intent=Intent.POLICY_SEARCH,
        confidence=0.95,
        entities={"query": "collision coverage"},
        action_type=ActionType.RAG_VISION,
        raw_text_hash="hash",
    )
    ctx = _ctx()
    payload = await route(parse_result, ctx, policy_provider=None)

    assert isinstance(payload, ResponsePayload)
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# Global exception boundary
# ---------------------------------------------------------------------------


async def test_unexpected_exception_returns_safe_payload() -> None:
    parse_result = IntentParseResult(
        intent=Intent.CLARIFY,
        confidence=0.95,
        entities={},
        action_type=ActionType.CLARIFICATION,
        raw_text_hash="hash",
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_clarification",
        AsyncMock(side_effect=RuntimeError("internal boom")),
    ):
        payload = await route(parse_result, ctx)

    assert isinstance(payload, ResponsePayload)
    assert "boom" not in payload.summary
    assert "RuntimeError" not in payload.summary
    assert payload.request_id == str(ctx.request_id)


async def test_mythos_error_caught_at_boundary() -> None:
    parse_result = IntentParseResult(
        intent=Intent.CLARIFY,
        confidence=0.95,
        entities={},
        action_type=ActionType.CLARIFICATION,
        raw_text_hash="hash",
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_clarification",
        AsyncMock(side_effect=MythosError("forced boundary escape")),
    ):
        payload = await route(parse_result, ctx)

    assert isinstance(payload, ResponsePayload)
    assert "forced boundary escape" not in payload.summary


async def test_timeout_error_caught_at_boundary() -> None:
    parse_result = IntentParseResult(
        intent=Intent.CLARIFY,
        confidence=0.95,
        entities={},
        action_type=ActionType.CLARIFICATION,
        raw_text_hash="hash",
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_clarification",
        AsyncMock(side_effect=TimeoutError()),
    ):
        payload = await route(parse_result, ctx)

    assert isinstance(payload, ResponsePayload)
    assert "timed out" in payload.summary.lower()
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# request_id preserved across all routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intent,action_type",
    [
        (Intent.CLARIFY, ActionType.CLARIFICATION),
        (Intent.UNKNOWN, ActionType.NOOP),
    ],
)
async def test_request_id_preserved(intent: Intent, action_type: ActionType) -> None:
    fixed_id = UUID("12345678-1234-5678-1234-567812345678")
    ctx = _ctx(request_id=fixed_id)
    parse_result = IntentParseResult(
        intent=intent,
        confidence=0.95,
        entities={},
        action_type=action_type,
        raw_text_hash="hash",
    )
    payload = await route(parse_result, ctx)
    assert payload.request_id == str(fixed_id)
