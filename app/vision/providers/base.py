"""Vision provider abstraction — wraps any multimodal LLM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class VisionAnalysisResult:
    """Result of a vision model inference call."""

    content: str
    model: str
    input_tokens: int = field(default=0)
    output_tokens: int = field(default=0)


class BaseVisionProvider(ABC):
    """Abstract vision provider interface."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short identifier for this provider (e.g. 'ollama')."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Fully-qualified model name used for inference."""

    @abstractmethod
    async def analyze(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        mime_type: str = "image/jpeg",
    ) -> VisionAnalysisResult:
        """Analyze an image and return the model's response.

        Parameters
        ----------
        image_bytes:
            Raw image bytes — never logged.
        prompt:
            Instruction for the model (describe, OCR, extract, etc.).
        mime_type:
            MIME type hint; providers may ignore if the format is auto-detected.
        """
