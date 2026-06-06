from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PolicySearchRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str
    tenant_id: UUID
    user_id: UUID
    max_results: int = Field(default=5, ge=1, le=20)


class PolicySummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    excerpt: str
    relevance: float = Field(ge=0.0, le=1.0)


class PolicySearchResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policies: list[PolicySummary]
    result_count: int


class ReceiptValidationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    image_url: str
    tenant_id: UUID
    user_id: UUID


class ReceiptValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_valid: bool
    total_amount: Decimal | None = None
    merchant: str | None = None
    transaction_date: date | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class DamageAnalysisRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    image_url: str
    tenant_id: UUID
    user_id: UUID
    claim_context: str | None = None


class DamageAnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    damage_detected: bool
    severity: str | None = None
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
