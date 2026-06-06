"""AI provider router.

Currently routes all requests to the local Ollama provider (free, no API key).
Structured for straightforward extension to OpenAI, Claude, Gemini, OpenRouter.
"""

from __future__ import annotations

from app.ai_gateway.providers.base import BaseAIProvider
from app.ai_gateway.providers.ollama_provider import OllamaProvider


class AIGatewayRouter:
    """Select the best available AI provider for a given request.

    Current policy: all task types → Ollama (local, zero-cost).

    Future routing hooks:
    - task_type == "vision"     → multimodal provider
    - task_type == "embedding"  → embedding-specialised provider
    - cost_tier == "premium"    → cloud provider with higher quality
    """

    def __init__(
        self,
        ollama: BaseAIProvider | None = None,
        # Future: openai: BaseAIProvider | None = None,
        # Future: claude: BaseAIProvider | None = None,
    ) -> None:
        self._ollama: BaseAIProvider = ollama or OllamaProvider()

    def select_provider(self, task_type: str) -> BaseAIProvider:
        """Return the provider to use for *task_type*.

        All task types currently resolve to Ollama.  ``task_type`` is accepted
        so callers don't need to change their interface when routing logic is
        extended.
        """
        # task_type will drive routing logic when more providers are added.
        del task_type
        return self._ollama

    @property
    def available_providers(self) -> dict[str, BaseAIProvider]:
        """Mapping of provider name → instance (useful for health checks)."""
        return {"ollama": self._ollama}
