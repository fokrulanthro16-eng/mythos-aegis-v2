"""Vision provider factory — selects the active provider from settings."""

from __future__ import annotations

from app.core.config import settings
from app.vision.providers.base import BaseVisionProvider


def get_vision_provider() -> BaseVisionProvider:
    """Return the configured vision provider.

    VISION_PROVIDER=ollama → OllamaVisionProvider (local inference, default)
    VISION_PROVIDER=gemini → GeminiVisionProvider (cloud, requires GEMINI_API_KEY)

    An unknown value falls back to Ollama so the service always starts.
    """
    name = settings.VISION_PROVIDER.lower().strip()

    if name == "gemini":
        from app.vision.providers.gemini_vision import GeminiVisionProvider

        return GeminiVisionProvider()

    if name == "fallback":
        from app.vision.providers.fallback_vision import FallbackVisionProvider

        return FallbackVisionProvider()

    from app.vision.providers.ollama_vision import OllamaVisionProvider

    return OllamaVisionProvider()
