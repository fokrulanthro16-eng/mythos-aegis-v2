"""Abstract base class for AI provider backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerateResult:
    """Normalised result returned by any provider's ``generate()`` call."""

    output: str
    input_tokens_estimate: int
    output_tokens_estimate: int
    model: str
    provider: str


class BaseAIProvider(ABC):
    """Interface that every AI provider backend must implement.

    Concrete providers (Ollama, OpenAI, Claude, Gemini …) subclass this and
    implement all abstract methods.  The router selects a provider at request
    time; the service layer only depends on this interface.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short stable identifier, e.g. ``'ollama'``, ``'openai'``."""
        ...  # pragma: no cover

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model name used when the caller does not specify one."""
        ...  # pragma: no cover

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int,
        model: str | None = None,
    ) -> GenerateResult:
        """Generate a completion for *prompt*.

        Prompt content must never be logged inside this method.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and operational."""
        ...  # pragma: no cover

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return the estimated USD cost for the given token counts."""
        ...  # pragma: no cover
