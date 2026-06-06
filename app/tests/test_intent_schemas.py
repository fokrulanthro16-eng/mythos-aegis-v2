import pytest
from pydantic import ValidationError

from app.intent.enums import ActionType, Intent
from app.intent.schemas import IntentParseResult


def _make(**overrides: object) -> IntentParseResult:
    defaults: dict[str, object] = {
        "intent": Intent.ANALYTICS_QUERY,
        "confidence": 0.90,
        "entities": {},
        "action_type": ActionType.SQL_ANALYTICS,
        "raw_text_hash": "abc123",
    }
    defaults.update(overrides)
    return IntentParseResult(**defaults)


def test_schema_is_immutable() -> None:
    result = _make()
    with pytest.raises(ValidationError):
        result.intent = Intent.UNKNOWN  # type: ignore[misc]


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        IntentParseResult(
            intent=Intent.ANALYTICS_QUERY,
            confidence=0.90,
            entities={},
            action_type=ActionType.SQL_ANALYTICS,
            raw_text_hash="abc123",
            surprise_field="oops",  # type: ignore[call-arg]
        )


def test_confidence_below_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        _make(confidence=-0.01)


def test_confidence_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        _make(confidence=1.01)


@pytest.mark.parametrize(
    "key",
    ["password", "token", "secret", "api_key", "credential", "auth"],
)
def test_unsafe_entity_keys_rejected(key: str) -> None:
    with pytest.raises(ValidationError, match="Unsafe entity key"):
        _make(entities={key: "some_value"})


def test_clarify_must_have_clarification_action() -> None:
    with pytest.raises(ValidationError, match="action_type CLARIFICATION"):
        _make(intent=Intent.CLARIFY, action_type=ActionType.NOOP)


def test_unknown_must_have_noop_action() -> None:
    with pytest.raises(ValidationError, match="action_type NOOP"):
        _make(intent=Intent.UNKNOWN, action_type=ActionType.SQL_ANALYTICS)


def test_valid_clarify_result() -> None:
    result = _make(
        intent=Intent.CLARIFY,
        action_type=ActionType.CLARIFICATION,
        confidence=0.10,
        entities={},
    )
    assert result.intent == Intent.CLARIFY
    assert result.action_type == ActionType.CLARIFICATION


def test_write_mutation_roundtrip() -> None:
    result = _make(intent=Intent.CANCEL_ORDER, action_type=ActionType.WRITE_MUTATION)
    assert result.intent == Intent.CANCEL_ORDER
    assert result.action_type == ActionType.WRITE_MUTATION


def test_rag_vision_roundtrip() -> None:
    result = _make(
        intent=Intent.VISION_DAMAGE_ANALYSIS, action_type=ActionType.RAG_VISION
    )
    assert result.intent == Intent.VISION_DAMAGE_ANALYSIS
    assert result.action_type == ActionType.RAG_VISION
