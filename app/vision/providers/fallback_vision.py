"""Fallback vision provider — returns a static offline response.

Used when VISION_PROVIDER=fallback.  Makes no network calls; suitable for
demos and CI environments where neither Ollama nor Gemini is available.
"""

from __future__ import annotations

import json as _json

from app.vision.providers.base import BaseVisionProvider, VisionAnalysisResult

_FALLBACK_CONTENT = _json.dumps(
    {
        "summary": (
            "Vision analysis is running in offline demo mode. "
            "No external service is required."
        ),
        "detected_objects": [],
        "observations": [
            "Fallback provider active — set VISION_PROVIDER=gemini for "
            "AI-powered cloud analysis."
        ],
    }
)


class FallbackVisionProvider(BaseVisionProvider):
    """Static offline provider — always returns the same canned response."""

    @property
    def provider_name(self) -> str:
        return "fallback"

    @property
    def model_name(self) -> str:
        return "fallback-static"

    async def analyze(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        mime_type: str = "image/jpeg",
    ) -> VisionAnalysisResult:
        return VisionAnalysisResult(
            content=_FALLBACK_CONTENT,
            model=self.model_name,
            input_tokens=0,
            output_tokens=0,
        )
