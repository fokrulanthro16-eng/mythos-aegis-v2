"""Pathway D — Clarification execution layer.

Execution-freeze guarantee: this pathway NEVER calls write, SQL, RAG, or
vision services.  It is a pure transformation from a parser result into a
structured clarification request directed at the user.

Entity-drop guarantee: entity data from the parser result is accepted but
immediately discarded.  No entity values appear in the response.
"""

import logging

from app.core.result import Result, Success
from app.intent.schemas import IntentParseResult
from app.pathways.clarification.schemas import (
    ClarificationRequest,
    ClarificationResponse,
)

logger = logging.getLogger(__name__)

_QUESTION_TEMPLATES: dict[str, str] = {
    "CLARIFY": (
        "I wasn't confident I understood your request. "
        "Could you please rephrase or provide more details?"
    ),
    "UNKNOWN": (
        "I couldn't determine what you'd like to do. "
        "Could you describe your request in a different way?"
    ),
}

_FALLBACK_QUESTION = (
    "Could you please clarify your request so I can assist you correctly?"
)

_DEFAULT_ACTIONS: list[str] = [
    "REPHRASE_REQUEST",
    "PROVIDE_MORE_DETAILS",
    "CANCEL",
]


def clarification_request_from_parse_result(
    parse_result: IntentParseResult,
) -> ClarificationRequest:
    """Adapt an IntentParseResult into a ClarificationRequest.

    The entities from the parser result are carried along so the service
    can explicitly drop them rather than silently ignoring them.
    """
    return ClarificationRequest(
        reason=str(parse_result.intent),
        original_query_hash=parse_result.raw_text_hash,
        entities=dict(parse_result.entities),
        suggested_actions=[],
    )


async def execute_clarification(
    request: ClarificationRequest,
) -> Result[ClarificationResponse]:
    """Return a structured clarification response.

    All entity data is dropped here.
    This function performs no I/O and calls no downstream services.
    """
    # Entity data is intentionally not accessed beyond this point.
    # The request carries entities only so callers can see they are dropped.
    question = _QUESTION_TEMPLATES.get(request.reason, _FALLBACK_QUESTION)
    actions: list[str] = (
        list(request.suggested_actions)
        if request.suggested_actions
        else list(_DEFAULT_ACTIONS)
    )
    response = ClarificationResponse(
        reason=request.reason,
        question=question,
        allowed_next_actions=actions,
    )
    logger.debug(
        "Clarification response built reason=%s actions=%s",
        request.reason,
        actions,
    )
    return Success(value=response)
