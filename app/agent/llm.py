"""Ollama chat client for the agent runtime.

Uses /api/chat for multi-turn conversations with proper role support.
Prompt content is never logged — only character counts.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.core.exceptions import AIProviderUnavailableError

logger = logging.getLogger(__name__)


class AgentLLMClient:
    """Thin async client for Ollama /api/chat."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.AGENT_MODEL
        self._timeout = timeout or settings.OLLAMA_TIMEOUT

    async def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
    ) -> str:
        """Send messages to Ollama and return the assistant reply.

        Never logs message content — only total character count.
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)
        logger.debug(
            "agent.llm.request model=%s messages=%d total_chars=%d",
            self._model,
            len(messages),
            total_chars,
        )

        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content: str = data["message"]["content"]
        except httpx.ConnectError as exc:
            raise AIProviderUnavailableError(
                f"Cannot connect to Ollama at {self._base_url}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise AIProviderUnavailableError("Ollama request timed out") from exc
        except (httpx.HTTPStatusError, KeyError, ValueError) as exc:
            raise AIProviderUnavailableError(
                f"Ollama returned an unexpected response: {exc}"
            ) from exc

        logger.debug(
            "agent.llm.response model=%s reply_chars=%d",
            self._model,
            len(content),
        )
        return content
