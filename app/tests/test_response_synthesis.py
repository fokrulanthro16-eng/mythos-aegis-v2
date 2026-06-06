"""Tests for app/response/synthesizer.py.

Verifies that the synthesizer:
- Produces correct summaries for each payload type.
- Generates markdown tables when SQL rows are present.
- Never exposes sensitive fields, stack traces, or SQL in failure messages.
- Always preserves request_id.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleViolation,
    DatabaseError,
    MythosError,
    SqlAirlockViolation,
    TenantIsolationError,
    ValidationError,
)
from app.core.result import Failure, Success
from app.pathways.clarification.schemas import ClarificationResponse
from app.pathways.rag_vision.schemas import (
    DamageAnalysisResult,
    PolicySearchResult,
    PolicySummary,
    ReceiptValidationResult,
)
from app.pathways.sql_airlock.schemas import AnalyticsResponse
from app.pathways.write.schemas import CancelOrderResponse
from app.response.synthesizer import _rows_to_markdown, synthesize

_RID = "req-00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Markdown table helper
# ---------------------------------------------------------------------------


def test_rows_to_markdown_empty_returns_none() -> None:
    assert _rows_to_markdown([]) is None


def test_rows_to_markdown_single_row() -> None:
    rows: list[dict[str, object]] = [{"id": 1, "status": "pending"}]
    md = _rows_to_markdown(rows)
    assert md is not None
    assert "| id | status |" in md
    assert "| --- | --- |" in md
    assert "| 1 | pending |" in md


def test_rows_to_markdown_multiple_rows() -> None:
    rows: list[dict[str, object]] = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]
    md = _rows_to_markdown(rows)
    assert md is not None
    lines = md.splitlines()
    assert len(lines) == 4  # header + separator + 2 data rows
    assert "Alice" in md
    assert "Bob" in md


# ---------------------------------------------------------------------------
# Analytics response synthesis
# ---------------------------------------------------------------------------


def test_analytics_no_rows_summary() -> None:
    result = Success(value=AnalyticsResponse(rows=[], row_count=0))
    payload = synthesize(result, request_id=_RID)
    assert "no results" in payload.summary.lower()
    assert payload.markdown_table is None
    assert payload.request_id == _RID


def test_analytics_with_rows_generates_table() -> None:
    rows: list[dict[str, object]] = [{"order_id": "abc", "status": "pending"}]
    result = Success(value=AnalyticsResponse(rows=rows, row_count=1))
    payload = synthesize(result, request_id=_RID)
    assert "1 row" in payload.summary
    assert payload.markdown_table is not None
    assert "order_id" in payload.markdown_table
    assert "abc" in payload.markdown_table


def test_analytics_plural_rows() -> None:
    rows: list[dict[str, object]] = [{"id": i} for i in range(5)]
    result = Success(value=AnalyticsResponse(rows=rows, row_count=5))
    payload = synthesize(result, request_id=_RID)
    assert "5 rows" in payload.summary


# ---------------------------------------------------------------------------
# Write (cancel order) response synthesis
# ---------------------------------------------------------------------------


def test_cancel_order_summary_contains_order_id() -> None:
    oid = uuid4()
    ts = datetime(2024, 6, 1, 14, 30, tzinfo=UTC)
    result = Success(
        value=CancelOrderResponse(
            operation_status="cancelled",
            order_id=oid,
            cancelled_at=ts,
        )
    )
    payload = synthesize(result, request_id=_RID)
    assert str(oid) in payload.summary
    assert "cancelled" in payload.summary.lower()
    assert payload.request_id == _RID


# ---------------------------------------------------------------------------
# Clarification response synthesis
# ---------------------------------------------------------------------------


def test_clarification_summary_is_question() -> None:
    result = Success(
        value=ClarificationResponse(
            reason="CLARIFY",
            question="Could you rephrase your request?",
            allowed_next_actions=["REPHRASE_REQUEST", "CANCEL"],
        )
    )
    payload = synthesize(result, request_id=_RID)
    assert "Could you rephrase" in payload.summary
    assert len(payload.warnings) > 0
    assert payload.request_id == _RID


# ---------------------------------------------------------------------------
# RAG — policy search response synthesis
# ---------------------------------------------------------------------------


def test_policy_search_no_results() -> None:
    result = Success(value=PolicySearchResult(policies=[], result_count=0))
    payload = synthesize(result, request_id=_RID)
    assert "no matching policies" in payload.summary.lower()


def test_policy_search_with_results() -> None:
    result = Success(
        value=PolicySearchResult(
            policies=[
                PolicySummary(
                    title="Standard Damage Coverage",
                    excerpt="Covers damage claims.",
                    relevance=0.92,
                )
            ],
            result_count=1,
        )
    )
    payload = synthesize(result, request_id=_RID)
    assert "Standard Damage Coverage" in payload.summary
    assert "92%" in payload.summary


# ---------------------------------------------------------------------------
# RAG — receipt validation synthesis
# ---------------------------------------------------------------------------


def test_receipt_valid_summary() -> None:
    result = Success(
        value=ReceiptValidationResult(
            is_valid=True,
            merchant="Test Shop",
            total_amount=Decimal("49.99"),
            confidence=0.95,
        )
    )
    payload = synthesize(result, request_id=_RID)
    assert "valid" in payload.summary.lower()
    assert "Test Shop" in payload.summary
    assert "49.99" in payload.summary


def test_receipt_invalid_summary() -> None:
    result = Success(value=ReceiptValidationResult(is_valid=False, confidence=0.60))
    payload = synthesize(result, request_id=_RID)
    assert "invalid" in payload.summary.lower()


# ---------------------------------------------------------------------------
# RAG — damage analysis synthesis
# ---------------------------------------------------------------------------


def test_damage_detected_summary() -> None:
    result = Success(
        value=DamageAnalysisResult(
            damage_detected=True,
            severity="minor",
            description="Small dent.",
            confidence=0.88,
        )
    )
    payload = synthesize(result, request_id=_RID)
    assert "damage detected" in payload.summary.lower()
    assert "minor" in payload.summary.lower()
    assert "Small dent." in payload.summary


def test_no_damage_summary() -> None:
    result = Success(
        value=DamageAnalysisResult(
            damage_detected=False,
            description="No visible damage.",
            confidence=0.99,
        )
    )
    payload = synthesize(result, request_id=_RID)
    assert "no damage" in payload.summary.lower()


# ---------------------------------------------------------------------------
# Failure synthesis — safe messages, no leakage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error,expected_fragment",
    [
        (AuthorizationError("forbidden"), "not authorized"),
        (TenantIsolationError("missing tenant"), "not authorized"),
        (SqlAirlockViolation("SELECT *"), "security policy"),
        (DatabaseError("pg error: select * from pg_tables"), "system error"),
    ],
)
def test_failure_produces_safe_message(
    error: MythosError, expected_fragment: str
) -> None:
    result: Failure = Failure(error=error, message=error.message)
    payload = synthesize(result, request_id=_RID)
    assert expected_fragment in payload.summary.lower()
    assert len(payload.warnings) > 0


def test_failure_never_leaks_sql() -> None:
    sql = "SELECT password_hash FROM users"
    result = Failure(
        error=DatabaseError("query failed"),
        message=f"Error running: {sql}",
    )
    payload = synthesize(result, request_id=_RID)
    assert "SELECT" not in payload.summary
    assert "password_hash" not in payload.summary
    assert sql not in payload.summary
    assert sql not in "\n".join(payload.warnings)


def test_failure_never_exposes_traceback() -> None:
    try:
        raise RuntimeError("internal kaboom")
    except RuntimeError as exc:
        result = Failure(error=exc, message="Traceback (most recent call last)")
    payload = synthesize(result, request_id=_RID)
    assert "Traceback" not in payload.summary
    assert "kaboom" not in payload.summary


def test_business_rule_violation_uses_message() -> None:
    result = Failure(
        error=BusinessRuleViolation("Order already cancelled"),
        message="Order already cancelled",
    )
    payload = synthesize(result, request_id=_RID)
    assert "Order already cancelled" in payload.summary


def test_validation_error_uses_message() -> None:
    result = Failure(
        error=ValidationError("Missing order_id"),
        message="Missing order_id",
    )
    payload = synthesize(result, request_id=_RID)
    assert "Missing order_id" in payload.summary


# ---------------------------------------------------------------------------
# request_id always preserved
# ---------------------------------------------------------------------------


def test_request_id_preserved_on_success() -> None:
    rid = str(uuid4())
    result = Success(value=AnalyticsResponse(rows=[], row_count=0))
    payload = synthesize(result, request_id=rid)
    assert payload.request_id == rid


def test_request_id_preserved_on_failure() -> None:
    rid = str(uuid4())
    result = Failure(error=DatabaseError("oops"), message="oops")
    payload = synthesize(result, request_id=rid)
    assert payload.request_id == rid


# ---------------------------------------------------------------------------
# Chart defaults to None when no chart data supplied
# ---------------------------------------------------------------------------


def test_chart_none_by_default_on_analytics() -> None:
    result = Success(value=AnalyticsResponse(rows=[], row_count=0))
    payload = synthesize(result, request_id=_RID)
    assert payload.chart is None
