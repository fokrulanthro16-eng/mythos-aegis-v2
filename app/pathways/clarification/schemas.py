from typing import Any

from pydantic import BaseModel, ConfigDict


class ClarificationRequest(BaseModel):
    """Input to the clarification pathway.

    Carries the parser's raw reason and entities.
    The service will drop all entity data before building the response.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: str
    original_query_hash: str
    entities: dict[str, Any]
    suggested_actions: list[str] = []


class ClarificationResponse(BaseModel):
    """Safe, entity-free response returned to the caller."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: str
    question: str
    allowed_next_actions: list[str]
