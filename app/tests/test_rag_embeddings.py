"""Tests for the Ollama embedding provider.

All HTTP calls are mocked — no running Ollama required.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import EmbeddingError
from app.rag.embeddings import OllamaEmbeddingProvider

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _mock_client(embedding: list[float]) -> AsyncMock:
    resp = MagicMock()
    resp.json.return_value = {"embedding": embedding}
    resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.post.return_value = resp
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


_FAKE_EMBEDDING = [0.1] * 768


# ── Construction ─────────────────────────────────────────────────────────────


def test_default_model_from_settings() -> None:
    provider = OllamaEmbeddingProvider(model="nomic-embed-text")
    assert provider.model == "nomic-embed-text"


def test_dimension_from_settings() -> None:
    provider = OllamaEmbeddingProvider()
    assert provider.dimension == 768


def test_no_api_key_attribute() -> None:
    provider = OllamaEmbeddingProvider()
    assert not hasattr(provider, "api_key")
    assert not hasattr(provider, "_api_key")


def test_custom_base_url() -> None:
    provider = OllamaEmbeddingProvider(base_url="http://custom:11434")
    assert "custom" in provider._base_url


# ── embed() happy path ────────────────────────────────────────────────────────


async def test_embed_returns_list_of_floats() -> None:
    client = _mock_client(_FAKE_EMBEDDING)
    with patch("httpx.AsyncClient", return_value=client):
        result = await OllamaEmbeddingProvider().embed("test text")
    assert isinstance(result, list)
    assert all(isinstance(v, float) for v in result)


async def test_embed_correct_dimension() -> None:
    client = _mock_client(_FAKE_EMBEDDING)
    with patch("httpx.AsyncClient", return_value=client):
        result = await OllamaEmbeddingProvider().embed("some text")
    assert len(result) == 768


async def test_embed_sends_to_correct_url() -> None:
    client = _mock_client(_FAKE_EMBEDDING)
    with patch("httpx.AsyncClient", return_value=client):
        await OllamaEmbeddingProvider(base_url="http://myhost:11434").embed("hi")
    url = client.post.call_args[0][0]
    assert url == "http://myhost:11434/api/embeddings"


async def test_embed_sends_model_in_payload() -> None:
    client = _mock_client(_FAKE_EMBEDDING)
    with patch("httpx.AsyncClient", return_value=client):
        await OllamaEmbeddingProvider(model="nomic-embed-text").embed("hi")
    payload = client.post.call_args[1]["json"]
    assert payload["model"] == "nomic-embed-text"


async def test_embed_sends_prompt_in_payload() -> None:
    client = _mock_client(_FAKE_EMBEDDING)
    with patch("httpx.AsyncClient", return_value=client):
        await OllamaEmbeddingProvider().embed("test query")
    payload = client.post.call_args[1]["json"]
    assert payload["prompt"] == "test query"


async def test_embed_no_auth_header() -> None:
    """Ollama is local — no authorization header must be sent."""
    client = _mock_client(_FAKE_EMBEDDING)
    with patch("httpx.AsyncClient", return_value=client):
        await OllamaEmbeddingProvider().embed("hi")
    kwargs = client.post.call_args[1]
    headers = kwargs.get("headers", {})
    assert "Authorization" not in headers
    assert "api-key" not in headers


# ── embed() — text never logged ───────────────────────────────────────────────


async def test_embed_does_not_log_content(caplog: pytest.LogCaptureFixture) -> None:
    sensitive = "CONFIDENTIAL_DOC_CONTENT_XYZ_NEVER_LOG"
    client = _mock_client(_FAKE_EMBEDDING)
    with (
        patch("httpx.AsyncClient", return_value=client),
        caplog.at_level(logging.DEBUG, logger="app.rag.embeddings"),
    ):
        await OllamaEmbeddingProvider().embed(sensitive)
    for record in caplog.records:
        assert sensitive not in record.getMessage()


# ── embed() — error paths ─────────────────────────────────────────────────────


async def test_connect_error_raises_embedding_error() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        client.post.side_effect = httpx.ConnectError("refused")
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = client
        with pytest.raises(EmbeddingError, match="not reachable"):
            await OllamaEmbeddingProvider().embed("text")


async def test_timeout_raises_embedding_error() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        client.post.side_effect = httpx.TimeoutException("timeout")
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = client
        with pytest.raises(EmbeddingError, match="timed out"):
            await OllamaEmbeddingProvider().embed("text")


async def test_http_status_error_raises_embedding_error() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        resp = MagicMock()
        resp.status_code = 500
        client = AsyncMock()
        client.post.side_effect = httpx.HTTPStatusError(
            "server error", request=MagicMock(), response=resp
        )
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = client
        with pytest.raises(EmbeddingError, match="HTTP 500"):
            await OllamaEmbeddingProvider().embed("text")


async def test_missing_embedding_field_raises_error() -> None:
    resp = MagicMock()
    resp.json.return_value = {"other_field": "no embedding here"}
    resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.post.return_value = resp
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with (
        patch("httpx.AsyncClient", return_value=client),
        pytest.raises(EmbeddingError, match="missing"),
    ):
        await OllamaEmbeddingProvider().embed("text")


# ── embed_batch() ─────────────────────────────────────────────────────────────


async def test_embed_batch_returns_one_per_text() -> None:
    client = _mock_client(_FAKE_EMBEDDING)
    with patch("httpx.AsyncClient", return_value=client):
        results = await OllamaEmbeddingProvider().embed_batch(["a", "b", "c"])
    assert len(results) == 3


async def test_embed_batch_each_result_correct_dimension() -> None:
    client = _mock_client(_FAKE_EMBEDDING)
    with patch("httpx.AsyncClient", return_value=client):
        results = await OllamaEmbeddingProvider().embed_batch(["x", "y"])
    for r in results:
        assert len(r) == 768
