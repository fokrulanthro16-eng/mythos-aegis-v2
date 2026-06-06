"""Local Ollama embedding provider.

Uses ``nomic-embed-text`` (or any configured model) via Ollama's
``POST /api/embeddings`` endpoint.  No API key is required.

Security invariants:
- Text content is NEVER written to any log.
- No Authorization header is sent.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.core.exceptions import EmbeddingError

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider:
    """Embed text using a local Ollama server."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.RAG_EMBEDDING_MODEL
        self._timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return settings.RAG_EMBEDDING_DIMENSION

    async def embed(self, text: str) -> list[float]:
        """Return an embedding vector for *text*.

        Text content is never logged — only character length is recorded.
        Raises ``EmbeddingError`` on any network or server failure.
        """
        url = f"{self._base_url}/api/embeddings"
        payload: dict[str, object] = {"model": self._model, "prompt": text}

        logger.debug(
            "embedding.request model=%s chars=%d",
            self._model,
            len(text),  # length only — content never logged
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.ConnectError as exc:
            raise EmbeddingError(
                f"Ollama not reachable at {self._base_url}. Run: ollama serve"
            ) from exc
        except httpx.TimeoutException as exc:
            raise EmbeddingError(
                f"Ollama timed out after {self._timeout}s during embedding."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(
                f"Ollama returned HTTP {exc.response.status_code} for embedding."
            ) from exc

        data: dict[str, object] = response.json()
        embedding = data.get("embedding")
        if not isinstance(embedding, list):
            raise EmbeddingError("Ollama response missing 'embedding' field.")

        logger.debug("embedding.done model=%s dim=%d", self._model, len(embedding))
        return [float(v) for v in embedding]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts sequentially.

        Ollama does not support batched embeddings; each text is sent
        in a separate request.
        """
        return [await self.embed(t) for t in texts]
