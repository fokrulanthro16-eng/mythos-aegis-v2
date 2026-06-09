"""Gemini Cloud Vision provider — calls the Gemini REST API via httpx."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import VisionProviderUnavailableError
from app.vision.providers.base import BaseVisionProvider, VisionAnalysisResult

logger = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/{model}:generateContent"
)

_STRUCTURED_PROMPT = (
    "Analyze this image and respond ONLY with valid JSON in exactly this structure:\n"
    '{"summary": "<one paragraph describing the image>", '
    '"detected_objects": ["<object>", "..."], '
    '"observations": ["<detail>", "..."]}\n'
    "Return ONLY the JSON object — no markdown fences, no extra text."
)


class GeminiVisionProvider(BaseVisionProvider):
    """Vision provider backed by the Gemini REST API.

    Requires GEMINI_API_KEY to be set in the environment.  When the key is
    absent the provider raises VisionProviderUnavailableError so callers can
    return a clean 503 without crashing the application.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self._model = model if model is not None else settings.GEMINI_MODEL
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    async def analyze(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        mime_type: str = "image/jpeg",
    ) -> VisionAnalysisResult:
        if not self._api_key:
            raise VisionProviderUnavailableError(
                "GEMINI_API_KEY is not configured. Set it in your .env file to enable "
                "cloud vision analysis."
            )

        instruction = prompt.strip() or _STRUCTURED_PROMPT
        b64_image = base64.b64encode(image_bytes).decode("ascii")

        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [
                        {"text": instruction},
                        {"inline_data": {"mime_type": mime_type, "data": b64_image}},
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        url = _GEMINI_URL.format(model=self._model)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, params={"key": self._api_key})

        if resp.status_code != 200:
            logger.warning(
                "gemini.vision.http_error status=%d body_prefix=%s",
                resp.status_code,
                resp.text[:200],
            )
            raise VisionProviderUnavailableError(
                f"Gemini API returned HTTP {resp.status_code}."
            )

        data: dict[str, Any] = resp.json()
        try:
            content: str = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise VisionProviderUnavailableError(
                "Gemini returned an unexpected response structure."
            ) from exc

        usage = data.get("usageMetadata", {})
        return VisionAnalysisResult(
            content=content,
            model=self._model,
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
        )
