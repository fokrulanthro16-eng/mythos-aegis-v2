"""End-to-end integration tests for the Mythos Aegis gateway.

Tests span from the FastAPI HTTP endpoint through the intent parser,
orchestrator, and pathway services to the synthesized ResponsePayload.
Where real services cannot be exercised (no live DB), pathways services
are mocked at the service-function level — the full routing and synthesis
path remains real.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.result import Failure, Success
from app.core.security_context import SecurityContext
from app.intent.enums import ActionType, Intent
from app.intent.schemas import IntentParseResult
from app.main import app
from app.orchestrator import route
from app.pathways.rag_vision.interfaces import MockPolicySearchProvider
from app.pathways.rag_vision.schemas import PolicySearchResult, PolicySummary
from app.pathways.sql_airlock.schemas import AnalyticsResponse
from app.pathways.write.mfa import MockMFAProvider
from app.pathways.write.schemas import CancelOrderResponse
from app.response.schemas import ResponsePayload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_PERMISSIONS = frozenset(
    {"orders.cancel", "analytics.read", "policies.read", "vision.analyze"}
)


def _ctx(*, request_id: UUID | None = None) -> SecurityContext:
    return SecurityContext(
        request_id=request_id or uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=_ALL_PERMISSIONS,
    )


def _parse(
    intent: Intent,
    action_type: ActionType,
    entities: dict[str, str] | None = None,
) -> IntentParseResult:
    return IntentParseResult(
        intent=intent,
        confidence=0.95,
        entities=entities or {},
        action_type=action_type,
        raw_text_hash="sha256-e2e-test",
    )


def _make_token(
    *,
    subject: UUID | None = None,
    tenant_id: UUID | None = None,
    permissions: list[str] | None = None,
    roles: list[str] | None = None,
    expired: bool = False,
    issuer: str | None = None,
    audience: str | list[str] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(subject or uuid4()),
        "tenant_id": str(tenant_id or uuid4()),
        "iss": issuer if issuer is not None else settings.JWT_ISSUER,
        "aud": audience if audience is not None else settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now - timedelta(seconds=1) if expired else now + timedelta(hours=1),
        "roles": roles if roles is not None else ["user"],
        "permissions": permissions
        if permissions is not None
        else list(_ALL_PERMISSIONS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Low confidence → clarification path (real parser, no mocks)
# ---------------------------------------------------------------------------


async def test_low_confidence_routes_to_clarification() -> None:
    """The real intent parser sends low-confidence inputs to CLARIFICATION."""
    from app.intent.parser import parse

    result = parse("xyzzy quux blorb florp garply")
    assert result.action_type == ActionType.CLARIFICATION

    ctx = _ctx()
    payload = await route(result, ctx)

    assert isinstance(payload, ResponsePayload)
    assert len(payload.summary) > 0
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# Analytics intent → SQL Airlock
# ---------------------------------------------------------------------------


async def test_analytics_intent_routes_to_sql_airlock() -> None:
    rows: list[dict[str, object]] = [
        {"order_id": "ord-001", "status": "pending"},
        {"order_id": "ord-002", "status": "shipped"},
    ]
    mock_analytics = Success(value=AnalyticsResponse(rows=rows, row_count=2))
    parse_result = _parse(
        Intent.ANALYTICS_QUERY,
        ActionType.SQL_ANALYTICS,
        {"sql": "SELECT id, status FROM orders"},
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_analytics_query",
        AsyncMock(return_value=mock_analytics),
    ):
        payload = await route(parse_result, ctx, session=AsyncMock())

    assert "2 rows" in payload.summary
    assert payload.markdown_table is not None
    assert "order_id" in payload.markdown_table
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# Cancel intent → Write pathway
# ---------------------------------------------------------------------------


async def test_cancel_intent_routes_to_write_pathway() -> None:
    oid = uuid4()
    ts = datetime(2024, 9, 15, 12, 0, tzinfo=UTC)
    mock_write = Success(
        value=CancelOrderResponse(
            operation_status="cancelled",
            order_id=oid,
            cancelled_at=ts,
        )
    )
    parse_result = _parse(
        Intent.CANCEL_ORDER,
        ActionType.WRITE_MUTATION,
        {"order_id": str(oid)},
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_cancel_order",
        AsyncMock(return_value=mock_write),
    ):
        payload = await route(
            parse_result,
            ctx,
            session=AsyncMock(),
            mfa_provider=MockMFAProvider(),
        )

    assert str(oid) in payload.summary
    assert "cancelled" in payload.summary.lower()
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# Policy intent → RAG pathway
# ---------------------------------------------------------------------------


async def test_policy_intent_routes_to_rag_pathway() -> None:
    mock_rag = Success(
        value=PolicySearchResult(
            policies=[
                PolicySummary(
                    title="Collision Coverage",
                    excerpt="Covers all collision events.",
                    relevance=0.91,
                )
            ],
            result_count=1,
        )
    )
    parse_result = _parse(
        Intent.POLICY_SEARCH,
        ActionType.RAG_VISION,
        {"query": "collision coverage"},
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.search_policies",
        AsyncMock(return_value=mock_rag),
    ):
        payload = await route(
            parse_result,
            ctx,
            policy_provider=MockPolicySearchProvider(),
        )

    assert "Collision Coverage" in payload.summary
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# Unexpected exception → safe warning, no internals leaked
# ---------------------------------------------------------------------------


async def test_unexpected_exception_produces_safe_payload() -> None:
    parse_result = _parse(Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS)
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_analytics_query",
        AsyncMock(side_effect=RuntimeError("connection pool exhausted")),
    ):
        payload = await route(parse_result, ctx, session=AsyncMock())

    assert isinstance(payload, ResponsePayload)
    assert "connection pool exhausted" not in payload.summary
    assert "RuntimeError" not in payload.summary
    assert len(payload.warnings) > 0
    assert payload.request_id == str(ctx.request_id)


# ---------------------------------------------------------------------------
# Sensitive data never returned
# ---------------------------------------------------------------------------


async def test_sensitive_data_never_in_sql_failure_response() -> None:
    sensitive_sql = "SELECT password_hash, api_token FROM users"
    mock_failure = Failure(
        error=Exception("query failed: " + sensitive_sql),
        message="query failed: " + sensitive_sql,
    )
    parse_result = _parse(
        Intent.ANALYTICS_QUERY,
        ActionType.SQL_ANALYTICS,
        {"sql": sensitive_sql},
    )
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_analytics_query",
        AsyncMock(return_value=mock_failure),
    ):
        payload = await route(parse_result, ctx, session=AsyncMock())

    serialized = payload.model_dump_json()
    assert "password_hash" not in serialized
    assert "api_token" not in serialized
    assert sensitive_sql not in serialized


async def test_stack_trace_never_in_response() -> None:
    parse_result = _parse(Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS)
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_analytics_query",
        AsyncMock(
            side_effect=ValueError("Traceback (most recent call last):\n  File...")
        ),
    ):
        payload = await route(parse_result, ctx, session=AsyncMock())

    assert "Traceback" not in payload.summary
    assert "Traceback" not in "\n".join(payload.warnings)


# ---------------------------------------------------------------------------
# Response synthesis — markdown table generated when rows exist
# ---------------------------------------------------------------------------


async def test_markdown_generated_when_rows_exist() -> None:
    rows: list[dict[str, object]] = [{"col_a": "val1", "col_b": "val2"}]
    mock_result = Success(value=AnalyticsResponse(rows=rows, row_count=1))
    parse_result = _parse(Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS)
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_analytics_query",
        AsyncMock(return_value=mock_result),
    ):
        payload = await route(parse_result, ctx, session=AsyncMock())

    assert payload.markdown_table is not None
    assert "col_a" in payload.markdown_table
    assert "val1" in payload.markdown_table


async def test_no_markdown_table_when_no_rows() -> None:
    mock_result = Success(value=AnalyticsResponse(rows=[], row_count=0))
    parse_result = _parse(Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS)
    ctx = _ctx()

    with patch(
        "app.orchestrator.execute_analytics_query",
        AsyncMock(return_value=mock_result),
    ):
        payload = await route(parse_result, ctx, session=AsyncMock())

    assert payload.markdown_table is None


# ---------------------------------------------------------------------------
# All pathways — request_id preserved
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intent,action_type,mock_target,mock_return",
    [
        (
            Intent.CLARIFY,
            ActionType.CLARIFICATION,
            None,
            None,
        ),
        (
            Intent.UNKNOWN,
            ActionType.NOOP,
            None,
            None,
        ),
    ],
)
async def test_request_id_preserved_pure_pathways(
    intent: Intent,
    action_type: ActionType,
    mock_target: str | None,
    mock_return: object | None,
) -> None:
    fixed_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    ctx = _ctx(request_id=fixed_id)
    parse_result = _parse(intent, action_type)
    payload = await route(parse_result, ctx)
    assert payload.request_id == str(fixed_id)


async def test_request_id_preserved_on_write_failure() -> None:
    """Even when no session is provided, request_id is in the payload."""
    fixed_id = UUID("11111111-2222-3333-4444-555555555555")
    ctx = _ctx(request_id=fixed_id)
    parse_result = _parse(Intent.CANCEL_ORDER, ActionType.WRITE_MUTATION)
    payload = await route(parse_result, ctx, session=None)
    assert payload.request_id == str(fixed_id)


async def test_request_id_preserved_on_sql_failure() -> None:
    fixed_id = UUID("aaaabbbb-cccc-dddd-eeee-ffffffffffff")
    ctx = _ctx(request_id=fixed_id)
    parse_result = _parse(Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS)
    payload = await route(parse_result, ctx, session=None)
    assert payload.request_id == str(fixed_id)


# ---------------------------------------------------------------------------
# FastAPI HTTP endpoint — POST /v1/route
# ---------------------------------------------------------------------------


async def test_route_endpoint_returns_200() -> None:
    token = _make_token()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "xyzzy quux blorb"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body
    assert "request_id" in body


async def test_route_endpoint_empty_message_returns_422() -> None:
    token = _make_token()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "  "},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 422


async def test_route_endpoint_response_shape() -> None:
    token = _make_token()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "cancel my order please"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["summary"], str)
    assert isinstance(body["warnings"], list)
    assert "chart" in body
    assert "markdown_table" in body


async def test_health_endpoint_still_works() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_route_endpoint_rejects_missing_token() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "hello"},
        )
    assert response.status_code == 401


async def test_route_endpoint_rejects_expired_token() -> None:
    token = _make_token(expired=True)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401
    body = response.json()
    assert token not in body.get("detail", "")


async def test_route_endpoint_rejects_invalid_token() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/route",
            json={"message": "hello"},
            headers={"Authorization": "Bearer not.a.real.jwt"},
        )
    assert response.status_code == 401
