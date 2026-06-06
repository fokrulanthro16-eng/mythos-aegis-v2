"""AI Gateway request and response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AIGatewayRequest(BaseModel):
    """Request payload for the AI generation endpoint.

    ``user_id`` is optional in the body — the authoritative identity is always
    taken from the JWT SecurityContext in the service layer, not this field.
    ``tenant_id`` is validated against SecurityContext.tenant_id to prevent
    cross-tenant spoofing.
    """

    tenant_id: UUID
    project_id: UUID | None = None
    user_id: UUID | None = None
    task_type: str = Field(default="generate", max_length=50)
    prompt: str = Field(min_length=1, max_length=32_000)
    max_tokens: int = Field(default=512, ge=1, le=4096)


class AIGatewayResponse(BaseModel):
    """Response from the AI generation endpoint."""

    model_config = ConfigDict(from_attributes=False)

    provider: str
    model: str
    output: str
    input_tokens_estimate: int
    output_tokens_estimate: int
    estimated_cost: float
    safety_warnings: list[str] = Field(default_factory=list)
