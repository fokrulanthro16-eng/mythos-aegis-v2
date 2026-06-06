"""Pathway C — RAG / Vision execution layer.

Routes POLICY_SEARCH, VISION_RECEIPT_VALIDATE, and VISION_DAMAGE_ANALYSIS
requests through their respective providers, then sanitizes every response
before it crosses the service boundary.

Sanitization rules enforced here:
- Internal document IDs are stripped.
- Raw embedding vectors are stripped.
- Provider trace identifiers are stripped.
- OCR engine internals (version, raw text) are stripped.
- Model identifiers and labels are stripped.
- Raw confidence scores are rounded to two decimal places.
"""

import logging

from app.core.exceptions import DatabaseError, MythosError
from app.core.result import Failure, Result, Success
from app.pathways.rag_vision.interfaces import (
    DamageVisionProvider,
    PolicySearchProvider,
    ReceiptOCRProvider,
    sanitize_damage_result,
    sanitize_policy_result,
    sanitize_receipt_result,
)
from app.pathways.rag_vision.schemas import (
    DamageAnalysisRequest,
    DamageAnalysisResult,
    PolicySearchRequest,
    PolicySearchResult,
    ReceiptValidationRequest,
    ReceiptValidationResult,
)

logger = logging.getLogger(__name__)


async def search_policies(
    request: PolicySearchRequest,
    provider: PolicySearchProvider,
) -> Result[PolicySearchResult]:
    """Execute a policy search and return a sanitized result."""
    try:
        raw = await provider.search(request)
        return Success(value=sanitize_policy_result(raw))
    except MythosError as exc:
        return Failure(error=exc, message=exc.message)
    except Exception:
        logger.exception("Policy search failed")
        return Failure(
            error=DatabaseError("Policy search failed"),
            message="A system error occurred during policy search",
        )


async def validate_receipt(
    request: ReceiptValidationRequest,
    provider: ReceiptOCRProvider,
) -> Result[ReceiptValidationResult]:
    """Validate a receipt image and return a sanitized result."""
    try:
        raw = await provider.validate(request)
        return Success(value=sanitize_receipt_result(raw))
    except MythosError as exc:
        return Failure(error=exc, message=exc.message)
    except Exception:
        logger.exception("Receipt validation failed")
        return Failure(
            error=DatabaseError("Receipt validation failed"),
            message="A system error occurred during receipt validation",
        )


async def analyze_damage(
    request: DamageAnalysisRequest,
    provider: DamageVisionProvider,
) -> Result[DamageAnalysisResult]:
    """Analyze a damage image and return a sanitized result."""
    try:
        raw = await provider.analyze(request)
        return Success(value=sanitize_damage_result(raw))
    except MythosError as exc:
        return Failure(error=exc, message=exc.message)
    except Exception:
        logger.exception("Damage analysis failed")
        return Failure(
            error=DatabaseError("Damage analysis failed"),
            message="A system error occurred during damage analysis",
        )
