"""Pathway C — RAG / Vision pathway tests.

Verifies that every service function:
  - Returns a sanitized public schema.
  - Strips internal document IDs, embedding vectors, and provider traces.
  - Strips OCR and vision-model internals.
  - Buckets raw confidence scores to user-facing values.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.exceptions import DatabaseError, MythosError
from app.core.result import Failure, Success
from app.pathways.rag_vision.interfaces import (
    MockDamageVisionProvider,
    MockPolicySearchProvider,
    MockReceiptOCRProvider,
    _RawDamageData,
    _RawPolicyMatch,
    _RawPolicySearchResult,
    _RawReceiptData,
    sanitize_damage_result,
    sanitize_policy_result,
    sanitize_receipt_result,
)
from app.pathways.rag_vision.schemas import (
    DamageAnalysisRequest,
    PolicySearchRequest,
    ReceiptValidationRequest,
)
from app.pathways.rag_vision.service import (
    analyze_damage,
    search_policies,
    validate_receipt,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _policy_request() -> PolicySearchRequest:
    return PolicySearchRequest(
        query="collision coverage", tenant_id=uuid4(), user_id=uuid4()
    )


def _receipt_request() -> ReceiptValidationRequest:
    return ReceiptValidationRequest(
        image_url="https://example.com/receipt.jpg",
        tenant_id=uuid4(),
        user_id=uuid4(),
    )


def _damage_request() -> DamageAnalysisRequest:
    return DamageAnalysisRequest(
        image_url="https://example.com/damage.jpg",
        tenant_id=uuid4(),
        user_id=uuid4(),
    )


# ---------------------------------------------------------------------------
# Policy search — sanitized result
# ---------------------------------------------------------------------------


async def test_policy_search_returns_sanitized_result() -> None:
    result = await search_policies(_policy_request(), MockPolicySearchProvider())

    assert isinstance(result, Success)
    assert result.value.result_count == 1
    assert result.value.policies[0].title == "Standard Damage Coverage"
    assert 0.0 <= result.value.policies[0].relevance <= 1.0


def test_policy_search_strips_internal_doc_id() -> None:
    raw = _RawPolicySearchResult(
        matches=[
            _RawPolicyMatch(
                internal_doc_id="INTERNAL-DOC-XYZ-001",
                title="Test Policy",
                excerpt="An excerpt.",
                raw_relevance_score=0.85,
                embedding_fragment=[0.1, 0.2],
            )
        ],
        query_embedding=[0.3, 0.4],
        provider_trace_id="TRACE-ABC-001",
    )
    sanitized = sanitize_policy_result(raw)
    serialized = sanitized.model_dump_json()

    assert "INTERNAL-DOC-XYZ-001" not in serialized
    assert "TRACE-ABC-001" not in serialized
    assert "embedding" not in serialized


def test_policy_search_strips_query_embedding() -> None:
    raw = _RawPolicySearchResult(
        matches=[],
        query_embedding=[0.111, 0.222, 0.333],
        provider_trace_id="TRACE-XYZ",
    )
    sanitized = sanitize_policy_result(raw)
    serialized = sanitized.model_dump_json()

    assert "query_embedding" not in serialized
    assert "0.111" not in serialized


def test_policy_search_buckets_raw_relevance_score() -> None:
    raw = _RawPolicySearchResult(
        matches=[
            _RawPolicyMatch(
                internal_doc_id="doc-001",
                title="Coverage",
                excerpt="Details.",
                raw_relevance_score=0.923456,
                embedding_fragment=[],
            )
        ],
        query_embedding=[],
        provider_trace_id="trace-001",
    )
    sanitized = sanitize_policy_result(raw)

    assert sanitized.policies[0].relevance == 0.92
    assert sanitized.policies[0].relevance != 0.923456


# ---------------------------------------------------------------------------
# Receipt validation — sanitized result
# ---------------------------------------------------------------------------


async def test_receipt_validation_returns_sanitized_result() -> None:
    result = await validate_receipt(_receipt_request(), MockReceiptOCRProvider())

    assert isinstance(result, Success)
    assert result.value.is_valid is True
    assert result.value.merchant == "Test Merchant"
    assert 0.0 <= result.value.confidence <= 1.0


def test_receipt_validation_strips_ocr_internals() -> None:
    from datetime import date
    from decimal import Decimal

    raw = _RawReceiptData(
        ocr_engine_version="tesseract-4.1.3",
        raw_ocr_text="RAW-OCR-TEXT-CONTENT",
        is_valid=True,
        total_amount=Decimal("99.99"),
        merchant="Shop",
        transaction_date=date(2024, 1, 1),
        raw_confidence_score=0.95,
    )
    sanitized = sanitize_receipt_result(raw)
    serialized = sanitized.model_dump_json()

    assert "tesseract-4.1.3" not in serialized
    assert "RAW-OCR-TEXT-CONTENT" not in serialized
    assert "ocr_engine_version" not in serialized
    assert "raw_ocr_text" not in serialized


def test_receipt_validation_buckets_confidence() -> None:
    from datetime import date
    from decimal import Decimal

    raw = _RawReceiptData(
        ocr_engine_version="v1",
        raw_ocr_text="text",
        is_valid=True,
        total_amount=Decimal("10.00"),
        merchant="M",
        transaction_date=date(2024, 1, 1),
        raw_confidence_score=0.9876,
    )
    sanitized = sanitize_receipt_result(raw)

    assert sanitized.confidence == 0.99
    assert sanitized.confidence != 0.9876


# ---------------------------------------------------------------------------
# Damage analysis — sanitized result
# ---------------------------------------------------------------------------


async def test_damage_analysis_returns_sanitized_result() -> None:
    result = await analyze_damage(_damage_request(), MockDamageVisionProvider())

    assert isinstance(result, Success)
    assert result.value.damage_detected is True
    assert result.value.severity == "minor"
    assert 0.0 <= result.value.confidence <= 1.0


def test_damage_analysis_strips_model_internals() -> None:
    raw = _RawDamageData(
        model_version="damage-model-v2.3",
        provider_request_id="PROV-REQ-789",
        raw_model_labels=["bumper_damage", "minor_dent"],
        damage_detected=True,
        severity="minor",
        description="Front bumper impact.",
        raw_confidence_score=0.85,
    )
    sanitized = sanitize_damage_result(raw)
    serialized = sanitized.model_dump_json()

    assert "damage-model-v2.3" not in serialized
    assert "PROV-REQ-789" not in serialized
    assert "bumper_damage" not in serialized
    assert "model_version" not in serialized
    assert "provider_request_id" not in serialized
    assert "raw_model_labels" not in serialized


def test_damage_analysis_buckets_confidence() -> None:
    raw = _RawDamageData(
        model_version="v1",
        provider_request_id="req-001",
        raw_model_labels=[],
        damage_detected=False,
        severity=None,
        description="No visible damage.",
        raw_confidence_score=0.8765,
    )
    sanitized = sanitize_damage_result(raw)

    assert sanitized.confidence == 0.88
    assert sanitized.confidence != 0.8765


# ---------------------------------------------------------------------------
# End-to-end internal-field leakage check
# ---------------------------------------------------------------------------


async def test_no_internal_fields_in_policy_search_response() -> None:
    """Mock returns specific known internal values; none must appear in output."""
    result = await search_policies(_policy_request(), MockPolicySearchProvider())
    assert isinstance(result, Success)
    serialized = result.value.model_dump_json()

    assert "INTERNAL-DOC-XYZ-001" not in serialized
    assert "TRACE-ABC-001" not in serialized
    assert "provider_trace_id" not in serialized
    assert "query_embedding" not in serialized


async def test_no_internal_fields_in_receipt_validation_response() -> None:
    result = await validate_receipt(_receipt_request(), MockReceiptOCRProvider())
    assert isinstance(result, Success)
    serialized = result.value.model_dump_json()

    assert "tesseract" not in serialized
    assert "RAW-OCR-TEXT-CONTENT" not in serialized


async def test_no_internal_fields_in_damage_analysis_response() -> None:
    result = await analyze_damage(_damage_request(), MockDamageVisionProvider())
    assert isinstance(result, Success)
    serialized = result.value.model_dump_json()

    assert "damage-model-v2.3" not in serialized
    assert "PROV-REQ-789" not in serialized
    assert "bumper_damage" not in serialized


# ---------------------------------------------------------------------------
# Provider failure → Failure result, no exception raised
# ---------------------------------------------------------------------------


async def test_policy_search_provider_error_returns_failure() -> None:
    broken = MockPolicySearchProvider()
    broken.search = AsyncMock(side_effect=RuntimeError("provider down"))  # type: ignore[method-assign]

    result = await search_policies(_policy_request(), broken)

    assert isinstance(result, Failure)
    assert isinstance(result.error, DatabaseError)


async def test_mythos_error_propagates_as_failure() -> None:
    broken = MockReceiptOCRProvider()
    broken.validate = AsyncMock(  # type: ignore[method-assign]
        side_effect=MythosError("internal rule violation")
    )

    result = await validate_receipt(_receipt_request(), broken)

    assert isinstance(result, Failure)
    assert isinstance(result.error, MythosError)
