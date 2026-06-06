"""Pathway D — Clarification pathway tests.

Verifies:
  - Entity data never appears in the response.
  - The response always contains a non-empty question and allowed_next_actions.
  - The service is a pure function — no downstream service calls required.
  - The adapter correctly converts IntentParseResult into ClarificationRequest.
"""

from app.core.result import Success
from app.intent.enums import ActionType, Intent
from app.intent.schemas import IntentParseResult
from app.pathways.clarification.schemas import ClarificationRequest
from app.pathways.clarification.service import (
    clarification_request_from_parse_result,
    execute_clarification,
)

# ---------------------------------------------------------------------------
# Entity-drop guarantee
# ---------------------------------------------------------------------------


async def test_clarification_drops_entities() -> None:
    request = ClarificationRequest(
        reason="CLARIFY",
        original_query_hash="abc123",
        entities={
            "secret_account": "ACC-99999",
            "target_user": "user@example.com",
            "ssn": "123-45-6789",
        },
        suggested_actions=[],
    )
    result = await execute_clarification(request)

    assert isinstance(result, Success)
    serialized = result.value.model_dump_json()

    assert "ACC-99999" not in serialized
    assert "user@example.com" not in serialized
    assert "123-45-6789" not in serialized
    assert "secret_account" not in serialized
    assert "target_user" not in serialized
    assert "ssn" not in serialized


# ---------------------------------------------------------------------------
# Structured question
# ---------------------------------------------------------------------------


async def test_clarification_asks_structured_question() -> None:
    request = ClarificationRequest(
        reason="UNKNOWN",
        original_query_hash="def456",
        entities={},
        suggested_actions=[],
    )
    result = await execute_clarification(request)

    assert isinstance(result, Success)
    assert isinstance(result.value.question, str)
    assert len(result.value.question.strip()) > 0


async def test_clarification_question_matches_known_reason() -> None:
    for reason in ("CLARIFY", "UNKNOWN"):
        request = ClarificationRequest(
            reason=reason,
            original_query_hash="hash",
            entities={},
            suggested_actions=[],
        )
        result = await execute_clarification(request)
        assert isinstance(result, Success)
        assert "?" in result.value.question


async def test_clarification_fallback_question_for_unknown_reason() -> None:
    request = ClarificationRequest(
        reason="SOME_NEW_REASON",
        original_query_hash="hash",
        entities={},
        suggested_actions=[],
    )
    result = await execute_clarification(request)

    assert isinstance(result, Success)
    assert len(result.value.question.strip()) > 0


# ---------------------------------------------------------------------------
# Execution-freeze — no downstream services called (pure function)
# ---------------------------------------------------------------------------


async def test_clarification_does_not_invoke_downstream_services() -> None:
    """Service must return Success with no I/O; no mocks needed."""
    request = ClarificationRequest(
        reason="CLARIFY",
        original_query_hash="pure-test",
        entities={"key": "value"},
        suggested_actions=[],
    )
    result = await execute_clarification(request)

    assert isinstance(result, Success)
    assert result.value.reason == "CLARIFY"


# ---------------------------------------------------------------------------
# allowed_next_actions
# ---------------------------------------------------------------------------


async def test_clarification_response_has_allowed_next_actions() -> None:
    request = ClarificationRequest(
        reason="CLARIFY",
        original_query_hash="hash",
        entities={},
        suggested_actions=[],
    )
    result = await execute_clarification(request)

    assert isinstance(result, Success)
    assert isinstance(result.value.allowed_next_actions, list)
    assert len(result.value.allowed_next_actions) > 0


async def test_clarification_uses_suggested_actions_when_provided() -> None:
    custom = ["DO_X", "DO_Y"]
    request = ClarificationRequest(
        reason="CLARIFY",
        original_query_hash="hash",
        entities={},
        suggested_actions=custom,
    )
    result = await execute_clarification(request)

    assert isinstance(result, Success)
    assert result.value.allowed_next_actions == custom


async def test_clarification_uses_default_actions_when_none_suggested() -> None:
    request = ClarificationRequest(
        reason="CLARIFY",
        original_query_hash="hash",
        entities={},
        suggested_actions=[],
    )
    result = await execute_clarification(request)

    assert isinstance(result, Success)
    assert "CANCEL" in result.value.allowed_next_actions


# ---------------------------------------------------------------------------
# Adapter: clarification_request_from_parse_result
# ---------------------------------------------------------------------------


def test_clarification_from_parse_result_adapter() -> None:
    parse_result = IntentParseResult(
        intent=Intent.CLARIFY,
        confidence=0.45,
        entities={"order_id": "ORD-999", "amount": "50.00"},
        action_type=ActionType.CLARIFICATION,
        raw_text_hash="sha256-abcd1234",
    )
    request = clarification_request_from_parse_result(parse_result)

    assert isinstance(request, ClarificationRequest)
    assert request.reason == "CLARIFY"
    assert request.original_query_hash == "sha256-abcd1234"
    assert request.entities == {"order_id": "ORD-999", "amount": "50.00"}
    assert request.suggested_actions == []


def test_adapter_preserves_entity_data_in_request() -> None:
    """Entities must be present in the request (so service can explicitly drop them)."""
    parse_result = IntentParseResult(
        intent=Intent.CLARIFY,
        confidence=0.12,
        entities={"pii_field": "sensitive-data"},
        action_type=ActionType.CLARIFICATION,
        raw_text_hash="sha256-xyz",
    )
    request = clarification_request_from_parse_result(parse_result)

    assert request.entities.get("pii_field") == "sensitive-data"


async def test_adapter_round_trip_drops_entities_in_response() -> None:
    """Full round-trip: adapter → service → entity values absent in response."""
    parse_result = IntentParseResult(
        intent=Intent.CLARIFY,
        confidence=0.38,
        entities={"credit_card": "4111111111111111"},
        action_type=ActionType.CLARIFICATION,
        raw_text_hash="sha256-round-trip",
    )
    request = clarification_request_from_parse_result(parse_result)
    result = await execute_clarification(request)

    assert isinstance(result, Success)
    serialized = result.value.model_dump_json()
    assert "4111111111111111" not in serialized
    assert "credit_card" not in serialized
