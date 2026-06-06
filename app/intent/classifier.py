import re
from dataclasses import dataclass

from app.intent.enums import ActionType, Intent

_CANCEL_RE = re.compile(r"\b(cancel|refund|void)\b", re.IGNORECASE)
_ANALYTICS_RE = re.compile(
    r"\b(report|analytics|sales|revenue|count|orders?\s+by\s+(date|month|year|week))\b"
    r"|\b(sales|revenue|analytics)\b",
    re.IGNORECASE,
)
_POLICY_RE = re.compile(r"\b(policy|handbook|sla|compliance)\b", re.IGNORECASE)
_RECEIPT_RE = re.compile(r"\b(receipt|invoice|ocr)\b", re.IGNORECASE)
_DAMAGE_RE = re.compile(r"\b(damage|defect|crack)\b", re.IGNORECASE)

_RULES: list[tuple[re.Pattern[str], Intent, ActionType, float]] = [
    (_CANCEL_RE, Intent.CANCEL_ORDER, ActionType.WRITE_MUTATION, 0.92),
    (_ANALYTICS_RE, Intent.ANALYTICS_QUERY, ActionType.SQL_ANALYTICS, 0.90),
    (_POLICY_RE, Intent.POLICY_SEARCH, ActionType.RAG_VISION, 0.90),
    (_RECEIPT_RE, Intent.VISION_RECEIPT_VALIDATE, ActionType.RAG_VISION, 0.91),
    (_DAMAGE_RE, Intent.VISION_DAMAGE_ANALYSIS, ActionType.RAG_VISION, 0.91),
]


@dataclass(frozen=True)
class ClassificationResult:
    intent: Intent
    action_type: ActionType
    confidence: float


def classify(text: str) -> ClassificationResult:
    for pattern, intent, action_type, confidence in _RULES:
        if pattern.search(text):
            return ClassificationResult(
                intent=intent,
                action_type=action_type,
                confidence=confidence,
            )
    return ClassificationResult(
        intent=Intent.UNKNOWN,
        action_type=ActionType.NOOP,
        confidence=0.10,
    )
