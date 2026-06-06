"""Ollama local AI provider.

Connects to a local Ollama server (default: http://localhost:11434).
No API key is required — Ollama runs entirely on the local machine.

Environment variables:
  OLLAMA_BASE_URL  — Ollama server base URL (default: http://localhost:11434)
  OLLAMA_MODEL     — model to use (default: llama3.1)
  OLLAMA_TIMEOUT   — HTTP timeout in seconds (default: 120.0)
"""

from __future__ import annotations

import logging

import httpx

from app.ai_gateway.providers.base import BaseAIProvider, GenerateResult
from app.core.config import settings
from app.core.exceptions import AIProviderUnavailableError

logger = logging.getLogger(__name__)


class OllamaProvider(BaseAIProvider):
    """AI provider backed by a local Ollama server.

    No API key is stored or transmitted — Ollama is unauthenticated by default.
    The raw prompt is never written to any log; only its character length is
    recorded for debugging.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.OLLAMA_MODEL
        self._timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT

    # ── BaseAIProvider interface ───────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def default_model(self) -> str:
        return self._model

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # Local inference — always zero cost.
        return 0.0

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int,
        model: str | None = None,
    ) -> GenerateResult:
        """Call ``POST /api/generate`` on the local Ollama server.

        Prompt content is never logged — only character length is recorded.
        """
        effective_model = model or self._model
        url = f"{self._base_url}/api/generate"
        payload: dict[str, object] = {
            "model": effective_model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }

        logger.debug(
            "ollama.generate model=%s prompt_chars=%d max_tokens=%d",
            effective_model,
            len(prompt),
            max_tokens,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.ConnectError as exc:
            raise AIProviderUnavailableError(
                f"Ollama is not reachable at {self._base_url}. Run: ollama serve"
            ) from exc
        except httpx.TimeoutException as exc:
            raise AIProviderUnavailableError(
                f"Ollama timed out after {self._timeout}s. "
                "The model may still be loading — try again shortly."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AIProviderUnavailableError(
                f"Ollama returned HTTP {exc.response.status_code}."
            ) from exc

        data: dict[str, object] = response.json()
        output = str(data.get("response", ""))

        # Rough 4-chars-per-token estimate; Ollama does not return exact counts.
        input_tokens = max(1, len(prompt) // 4)
        output_tokens = max(0, len(output) // 4)

        return GenerateResult(
            output=output,
            input_tokens_estimate=input_tokens,
            output_tokens_estimate=output_tokens,
            model=effective_model,
            provider=self.provider_name,
        )

    async def health_check(self) -> bool:
        """Return ``True`` if the Ollama HTTP server is responding."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
