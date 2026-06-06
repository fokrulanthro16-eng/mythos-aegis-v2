"""Response synthesizer — converts any pathway result into a ResponsePayload.

Security guarantees enforced here:
- Failure messages never include SQL strings, stack traces, or database details.
- Sensitive field names (password, token, secret, …) never appear in summaries.
- Internal IDs and provider-specific metadata are already stripped by the
  pathway layer; the synthesizer operates only on sanitized Pydantic values.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleViolation,
    SqlAirlockViolation,
    TenantIsolationError,
    ValidationError,
)
from app.core.result import Failure, Result
from app.pathways.clarification.schemas import ClarificationResponse
from app.pathways.rag_vision.schemas import (
    DamageAnalysisResult,
    PolicySearchResult,
    ReceiptValidationResult,
)
from app.pathways.sql_airlock.schemas import AnalyticsResponse
from app.pathways.write.schemas import CancelOrderResponse
from app.response.schemas import ResponsePayload

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Markdown table builder
# ---------------------------------------------------------------------------


def _rows_to_markdown(rows: list[dict[str, object]]) -> str | None:
    if not rows:
        return None
    headers = list(rows[0].keys())
    header_row = "| " + " | ".join(str(h) for h in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    data_rows = [
        "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |" for row in rows
    ]
    return "\n".join([header_row, separator, *data_rows])


# ---------------------------------------------------------------------------
# Safe failure messaging — never leaks SQL, tracebacks, or DB details
# ---------------------------------------------------------------------------


def _safe_failure_message(failure: Failure) -> str:
    err = failure.error
    if isinstance(err, (AuthorizationError, TenantIsolationError)):
        return "This action is not authorized."
    if isinstance(err, BusinessRuleViolation):
        return failure.message or "The request violates a business rule."
    if isinstance(err, SqlAirlockViolation):
        return "The query was rejected by the security policy."
    if isinstance(err, ValidationError):
        return failure.message or "The request is invalid."
    return "A system error occurred. Please try again."


# ---------------------------------------------------------------------------
# Per-payload-type synthesis helpers
# ---------------------------------------------------------------------------


def _from_analytics(value: AnalyticsResponse, *, request_id: str) -> ResponsePayload:
    md_table = _rows_to_markdown(list(value.rows)) if value.rows else None
    if value.row_count == 0:
        summary = "Query returned no results."
    elif value.row_count == 1:
        summary = "Query returned 1 row."
    else:
        summary = f"Query returned {value.row_count} rows."
    return ResponsePayload(
        summary=summary,
        markdown_table=md_table,
        request_id=request_id,
    )


def _from_cancel_order(
    value: CancelOrderResponse, *, request_id: str
) -> ResponsePayload:
    ts = value.cancelled_at.strftime("%Y-%m-%d %H:%M UTC")
    return ResponsePayload(
        summary=(
            f"Order {value.order_id} has been successfully cancelled."
            f" Cancelled at: {ts}."
        ),
        request_id=request_id,
    )


def _from_clarification(
    value: ClarificationResponse, *, request_id: str
) -> ResponsePayload:
    actions_str = ", ".join(value.allowed_next_actions)
    return ResponsePayload(
        summary=value.question,
        warnings=[f"Clarification required. Suggested actions: {actions_str}"],
        request_id=request_id,
    )


def _from_policy_search(
    value: PolicySearchResult, *, request_id: str
) -> ResponsePayload:
    if not value.policies:
        return ResponsePayload(
            summary="No matching policies found.",
            request_id=request_id,
        )
    noun = "policy" if value.result_count == 1 else "policies"
    lines = [f"Found {value.result_count} matching {noun}:"]
    for i, policy in enumerate(value.policies, 1):
        pct = f"{policy.relevance:.0%}"
        lines.append(f"{i}. **{policy.title}** (relevance: {pct})")
        lines.append(f"   {policy.excerpt}")
    return ResponsePayload(
        summary="\n".join(lines),
        request_id=request_id,
    )


def _from_receipt_validation(
    value: ReceiptValidationResult, *, request_id: str
) -> ResponsePayload:
    status = "valid" if value.is_valid else "invalid"
    pct = f"{value.confidence:.0%}"
    parts: list[str] = [f"Receipt is {status} (confidence: {pct})."]
    if value.merchant:
        parts.append(f"Merchant: {value.merchant}.")
    if value.total_amount is not None:
        parts.append(f"Amount: {value.total_amount}.")
    return ResponsePayload(
        summary=" ".join(parts),
        request_id=request_id,
    )


def _from_damage_analysis(
    value: DamageAnalysisResult, *, request_id: str
) -> ResponsePayload:
    detected = "Damage detected" if value.damage_detected else "No damage detected"
    pct = f"{value.confidence:.0%}"
    parts: list[str] = [f"{detected} (confidence: {pct})."]
    if value.severity:
        parts.append(f"Severity: {value.severity}.")
    parts.append(value.description)
    return ResponsePayload(
        summary=" ".join(parts),
        request_id=request_id,
    )


def _from_value(value: object, *, request_id: str) -> ResponsePayload:
    if isinstance(value, AnalyticsResponse):
        return _from_analytics(value, request_id=request_id)
    if isinstance(value, CancelOrderResponse):
        return _from_cancel_order(value, request_id=request_id)
    if isinstance(value, ClarificationResponse):
        return _from_clarification(value, request_id=request_id)
    if isinstance(value, PolicySearchResult):
        return _from_policy_search(value, request_id=request_id)
    if isinstance(value, ReceiptValidationResult):
        return _from_receipt_validation(value, request_id=request_id)
    if isinstance(value, DamageAnalysisResult):
        return _from_damage_analysis(value, request_id=request_id)
    logger.warning("synthesize: unknown result value type %s", type(value).__name__)
    return ResponsePayload(
        summary="Request completed.",
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def synthesize(result: Result[Any], *, request_id: str) -> ResponsePayload:
    """Convert a pathway Result into a ResponsePayload.

    This function never raises; all failure paths produce safe messages.
    """
    if isinstance(result, Failure):
        msg = _safe_failure_message(result)
        return ResponsePayload(
            summary=msg,
            warnings=[msg],
            request_id=request_id,
        )
    return _from_value(result.value, request_id=request_id)
