"""Provider interfaces and raw internal types for the RAG / Vision pathway.

The raw types (_Raw*) represent what external AI/OCR providers actually return.
They contain internal fields (document IDs, embeddings, model versions, traces)
that the service layer must strip before exposing results to callers.

Mock implementations are provided for testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.pathways.rag_vision.schemas import (
    DamageAnalysisRequest,
    DamageAnalysisResult,
    PolicySearchRequest,
    PolicySearchResult,
    PolicySummary,
    ReceiptValidationRequest,
    ReceiptValidationResult,
)

# ---------------------------------------------------------------------------
# Raw internal types — never leave the service boundary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _RawPolicyMatch:
    internal_doc_id: str  # private document UUID — must be stripped
    title: str
    excerpt: str
    raw_relevance_score: float  # cosine similarity — must be bucketed
    embedding_fragment: list[float]  # re-ranking vector — must be stripped


@dataclass(frozen=True)
class _RawPolicySearchResult:
    matches: list[_RawPolicyMatch]
    query_embedding: list[float]  # query vector — must be stripped
    provider_trace_id: str  # upstream trace ID — must be stripped


@dataclass(frozen=True)
class _RawReceiptData:
    ocr_engine_version: str  # engine identifier — must be stripped
    raw_ocr_text: str  # OCR dump — must be stripped
    is_valid: bool
    total_amount: Decimal | None
    merchant: str | None
    transaction_date: date | None
    raw_confidence_score: float  # model confidence — must be bucketed


@dataclass(frozen=True)
class _RawDamageData:
    model_version: str  # model identifier — must be stripped
    provider_request_id: str  # upstream request ID — must be stripped
    raw_model_labels: list[str]  # raw classifier labels — must be stripped
    damage_detected: bool
    severity: str | None
    description: str
    raw_confidence_score: float  # model confidence — must be bucketed


# ---------------------------------------------------------------------------
# Abstract provider interfaces
# ---------------------------------------------------------------------------


class PolicySearchProvider(ABC):
    @abstractmethod
    async def search(self, request: PolicySearchRequest) -> _RawPolicySearchResult: ...


class ReceiptOCRProvider(ABC):
    @abstractmethod
    async def validate(self, request: ReceiptValidationRequest) -> _RawReceiptData: ...


class DamageVisionProvider(ABC):
    @abstractmethod
    async def analyze(self, request: DamageAnalysisRequest) -> _RawDamageData: ...


# ---------------------------------------------------------------------------
# Mock implementations for testing
# The mock data intentionally includes specific internal values so that
# tests can verify those values are stripped by the service layer.
# ---------------------------------------------------------------------------


class MockPolicySearchProvider(PolicySearchProvider):
    async def search(self, request: PolicySearchRequest) -> _RawPolicySearchResult:
        return _RawPolicySearchResult(
            matches=[
                _RawPolicyMatch(
                    internal_doc_id="INTERNAL-DOC-XYZ-001",
                    title="Standard Damage Coverage",
                    excerpt="This policy covers standard vehicle damage claims.",
                    raw_relevance_score=0.923456,
                    embedding_fragment=[0.112, 0.334, 0.556],
                ),
            ],
            query_embedding=[0.111, 0.222, 0.333, 0.444],
            provider_trace_id="TRACE-ABC-001",
        )


class MockReceiptOCRProvider(ReceiptOCRProvider):
    async def validate(self, request: ReceiptValidationRequest) -> _RawReceiptData:
        return _RawReceiptData(
            ocr_engine_version="tesseract-4.1.3",
            raw_ocr_text="RAW-OCR-TEXT-CONTENT",
            is_valid=True,
            total_amount=Decimal("42.50"),
            merchant="Test Merchant",
            transaction_date=date(2024, 3, 15),
            raw_confidence_score=0.9876,
        )


class MockDamageVisionProvider(DamageVisionProvider):
    async def analyze(self, request: DamageAnalysisRequest) -> _RawDamageData:
        return _RawDamageData(
            model_version="damage-model-v2.3",
            provider_request_id="PROV-REQ-789",
            raw_model_labels=["bumper_damage", "minor_dent"],
            damage_detected=True,
            severity="minor",
            description="Minor dent on the front bumper area.",
            raw_confidence_score=0.8765,
        )


# ---------------------------------------------------------------------------
# Sanitization helpers  (used by service.py)
# ---------------------------------------------------------------------------


def sanitize_policy_result(raw: _RawPolicySearchResult) -> PolicySearchResult:
    """Build a public PolicySearchResult, stripping all internal fields."""
    policies = [
        PolicySummary(
            title=match.title,
            excerpt=match.excerpt,
            relevance=round(max(0.0, min(1.0, match.raw_relevance_score)), 2),
        )
        for match in raw.matches
    ]
    return PolicySearchResult(policies=policies, result_count=len(policies))


def sanitize_receipt_result(raw: _RawReceiptData) -> ReceiptValidationResult:
    """Build a public ReceiptValidationResult, stripping all OCR internals."""
    return ReceiptValidationResult(
        is_valid=raw.is_valid,
        total_amount=raw.total_amount,
        merchant=raw.merchant,
        transaction_date=raw.transaction_date,
        confidence=round(max(0.0, min(1.0, raw.raw_confidence_score)), 2),
    )


def sanitize_damage_result(raw: _RawDamageData) -> DamageAnalysisResult:
    """Build a public DamageAnalysisResult, stripping all model internals."""
    return DamageAnalysisResult(
        damage_detected=raw.damage_detected,
        severity=raw.severity,
        description=raw.description,
        confidence=round(max(0.0, min(1.0, raw.raw_confidence_score)), 2),
    )
