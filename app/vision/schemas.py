"""Pydantic schemas for the Vision Intelligence API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

# ── Image analysis ────────────────────────────────────────────────────────────


class VisionAnalyzeResponse(BaseModel):
    """Response from POST /v1/vision/analyze."""

    analysis: str
    summary: str
    provider: str
    model: str
    filename: str
    file_type: str
    index_status: str | None = None
    document_id: UUID | None = None


# ── PDF / document extraction ─────────────────────────────────────────────────


class PDFExtractResponse(BaseModel):
    """Response from POST /v1/vision/extract."""

    filename: str
    page_count: int
    text_pages: list[str]
    total_chars: int
    index_status: str | None = None
    document_id: UUID | None = None


# ── OCR convenience ───────────────────────────────────────────────────────────


class OCRResponse(BaseModel):
    """Structured OCR result (extracted text only)."""

    filename: str
    text: str
    model: str
    char_count: int = Field(description="Number of characters extracted")


# ── Gemini Cloud Vision ───────────────────────────────────────────────────────


class GeminiAnalyzeResponse(BaseModel):
    """Structured response from POST /vision/analyze (Gemini Cloud Vision)."""

    summary: str
    detected_objects: list[str]
    observations: list[str]
