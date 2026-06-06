import hashlib
import logging
import re

from app.core.config import settings
from app.intent.classifier import classify
from app.intent.enums import ActionType, Intent
from app.intent.schemas import IntentParseResult

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.strip()).lower()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse(raw_text: str) -> IntentParseResult:
    if not raw_text or not raw_text.strip():
        raise ValueError("Input text must not be empty.")

    normalized = _normalize(raw_text)
    text_hash = _sha256(raw_text)
    result = classify(normalized)

    if result.confidence < settings.INTENT_CONFIDENCE_THRESHOLD:
        logger.info(
            "Low confidence %.2f for input (len=%d), routing to CLARIFY",
            result.confidence,
            len(normalized),
        )
        return IntentParseResult(
            intent=Intent.CLARIFY,
            confidence=result.confidence,
            entities={},
            action_type=ActionType.CLARIFICATION,
            raw_text_hash=text_hash,
        )

    logger.info(
        "Classified input as %s (confidence=%.2f, len=%d)",
        result.intent,
        result.confidence,
        len(normalized),
    )
    return IntentParseResult(
        intent=result.intent,
        confidence=result.confidence,
        entities={},
        action_type=result.action_type,
        raw_text_hash=text_hash,
    )
