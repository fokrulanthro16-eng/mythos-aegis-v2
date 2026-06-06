from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.intent.enums import ActionType, Intent

_UNSAFE_ENTITY_KEYS: frozenset[str] = frozenset(
    {"password", "token", "secret", "api_key", "credential", "auth"}
)


class IntentParseResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    intent: Intent
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    entities: dict[str, Any]
    action_type: ActionType
    raw_text_hash: str

    @field_validator("entities")
    @classmethod
    def validate_entity_keys(cls, v: dict[str, Any]) -> dict[str, Any]:
        for key in v:
            normalized = key.lower()
            if normalized in _UNSAFE_ENTITY_KEYS or any(
                unsafe in normalized for unsafe in _UNSAFE_ENTITY_KEYS
            ):
                raise ValueError(
                    f"Unsafe entity key detected: '{key}'. "
                    "Keys containing sensitive identifiers are forbidden."
                )
        return v

    @model_validator(mode="after")
    def validate_action_consistency(self) -> Self:
        if (
            self.intent == Intent.CLARIFY
            and self.action_type != ActionType.CLARIFICATION
        ):
            raise ValueError("Intent CLARIFY must have action_type CLARIFICATION")
        if self.intent == Intent.UNKNOWN and self.action_type != ActionType.NOOP:
            raise ValueError("Intent UNKNOWN must have action_type NOOP")
        return self
