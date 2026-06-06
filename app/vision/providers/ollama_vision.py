"""Ollama vision provider — Qwen2.5-VL / Llama 3.2 Vision.

Uses the Ollama /api/chat endpoint with base64-encoded image payloads.
Image bytes are NEVER logged — only size metadata.
"""

from __future__ import annotations

import base64
import logging

import httpx

from app.core.config import settings
from app.core.exceptions import VisionProviderUnavailableError
from app.vision.providers.base import BaseVisionProvider, VisionAnalysisResult

logger = logging.getLogger(__name__)


class OllamaVisionProvider(BaseVisionProvider):
    """Vision provider backed by Ollama (Qwen2.5-VL primary, Llama 3.2 fallback)."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.VISION_MODEL
        self._timeout = timeout or settings.VISION_ANALYSIS_TIMEOUT

    @property
    def provider_name(self) -> str:
        return "ollama"

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
        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }

        logger.debug(
            "vision.ollama.request model=%s image_bytes=%d prompt_chars=%d",
            self._model,
            len(image_bytes),
            len(prompt),
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.ConnectError as exc:
            raise VisionProviderUnavailableError(
                f"Cannot reach Ollama at {self._base_url}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise VisionProviderUnavailableError(
                "Ollama vision request timed out"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise VisionProviderUnavailableError(
                f"Ollama returned HTTP {exc.response.status_code}"
            ) from exc

        content: str = data.get("message", {}).get("content", "")
        usage: dict[str, int] = data.get("usage", {})

        logger.debug(
            "vision.ollama.response model=%s output_chars=%d",
            self._model,
            len(content),
        )

        return VisionAnalysisResult(
            content=content,
            model=self._model,
            input_tokens=usage.get("prompt_eval_count", 0),
            output_tokens=usage.get("eval_count", 0),
        )
