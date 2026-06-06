import hashlib

import pytest
from pydantic import ValidationError

from app.intent.enums import ActionType, Intent
from app.intent.parser import parse


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse("")


def test_whitespace_only_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse("   ")


def test_cancel_order_routing() -> None:
    result = parse("I need to cancel my order #1234")
    assert result.intent == Intent.CANCEL_ORDER
    assert result.action_type == ActionType.WRITE_MUTATION
    assert result.confidence >= 0.85


def test_refund_routes_to_cancel_order() -> None:
    result = parse("Please refund my purchase")
    assert result.intent == Intent.CANCEL_ORDER
    assert result.action_type == ActionType.WRITE_MUTATION


def test_analytics_query_routing() -> None:
    result = parse("Show me the sales report by date for last month")
    assert result.intent == Intent.ANALYTICS_QUERY
    assert result.action_type == ActionType.SQL_ANALYTICS
    assert result.confidence >= 0.85


def test_policy_search_routing() -> None:
    result = parse("What does the SLA policy say about response times?")
    assert result.intent == Intent.POLICY_SEARCH
    assert result.action_type == ActionType.RAG_VISION
    assert result.confidence >= 0.85


def test_vision_receipt_routing() -> None:
    result = parse("Please validate this receipt from the vendor")
    assert result.intent == Intent.VISION_RECEIPT_VALIDATE
    assert result.action_type == ActionType.RAG_VISION
    assert result.confidence >= 0.85


def test_vision_damage_routing() -> None:
    result = parse("There is a crack in the product")
    assert result.intent == Intent.VISION_DAMAGE_ANALYSIS
    assert result.action_type == ActionType.RAG_VISION
    assert result.confidence >= 0.85


def test_low_confidence_routes_to_clarify() -> None:
    result = parse("blurb wibble frobnicate")
    assert result.intent == Intent.CLARIFY
    assert result.action_type == ActionType.CLARIFICATION
    assert result.entities == {}
    assert result.confidence < 0.85


def test_low_confidence_clears_entities() -> None:
    result = parse("something completely ambiguous xyz")
    assert result.entities == {}
    assert result.intent == Intent.CLARIFY


def test_result_is_immutable() -> None:
    result = parse("cancel my order")
    with pytest.raises(ValidationError):
        result.intent = Intent.UNKNOWN  # type: ignore[misc]


def test_raw_text_hash_is_sha256() -> None:
    text = "cancel my order"
    result = parse(text)
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert result.raw_text_hash == expected


def test_hash_uses_raw_not_normalized_text() -> None:
    text = "  Cancel MY Order  "
    result = parse(text)
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert result.raw_text_hash == expected


def test_clarify_result_is_immutable() -> None:
    result = parse("blurb wibble frobnicate")
    with pytest.raises(ValidationError):
        result.action_type = ActionType.NOOP  # type: ignore[misc]
