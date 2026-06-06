"""Tests for the Ollama AI provider.

All HTTP calls to Ollama are mocked — no running Ollama instance required.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ai_gateway.providers.base import GenerateResult
from app.ai_gateway.providers.ollama_provider import OllamaProvider
from app.core.exceptions import AIProviderUnavailableError

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def ollama_json_response() -> dict[str, object]:
    return {"response": "Paris is the capital of France.", "done": True}


@pytest.fixture
def mock_http_response(ollama_json_response: dict[str, object]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = ollama_json_response
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def mock_client(mock_http_response: MagicMock) -> AsyncMock:
    client = AsyncMock()
    client.post.return_value = mock_http_response
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.fixture
def mock_health_client() -> AsyncMock:
    resp = MagicMock()
    resp.status_code = 200
    client = AsyncMock()
    client.get.return_value = resp
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ── Provider construction ─────────────────────────────────────────────────────


def test_provider_name_is_ollama() -> None:
    assert OllamaProvider().provider_name == "ollama"


def test_default_model_from_settings() -> None:
    provider = OllamaProvider(model="phi3")
    assert provider.default_model == "phi3"


def test_cost_is_always_zero() -> None:
    provider = OllamaProvider()
    assert provider.estimate_cost(1_000, 500) == 0.0


def test_cost_zero_for_large_token_counts() -> None:
    provider = OllamaProvider()
    assert provider.estimate_cost(1_000_000, 1_000_000) == 0.0


def test_no_api_key_attribute() -> None:
    """OllamaProvider must not store any API key."""
    provider = OllamaProvider()
    assert not hasattr(provider, "api_key")
    assert not hasattr(provider, "_api_key")


def test_custom_base_url_stored() -> None:
    provider = OllamaProvider(base_url="http://custom-host:11434")
    assert "custom-host" in provider._base_url


# ── generate() — happy path ───────────────────────────────────────────────────


async def test_generate_returns_result(mock_client: AsyncMock) -> None:
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await OllamaProvider().generate(
            "What is the capital of France?", max_tokens=50
        )
    assert isinstance(result, GenerateResult)
    assert result.output == "Paris is the capital of France."
    assert result.provider == "ollama"


async def test_generate_uses_correct_url(mock_client: AsyncMock) -> None:
    with patch("httpx.AsyncClient", return_value=mock_client):
        await OllamaProvider(base_url="http://myhost:11434").generate(
            "hi", max_tokens=10
        )
    call_url = mock_client.post.call_args[0][0]
    assert call_url == "http://myhost:11434/api/generate"


async def test_generate_sends_model_in_payload(mock_client: AsyncMock) -> None:
    with patch("httpx.AsyncClient", return_value=mock_client):
        await OllamaProvider(model="mistral").generate("hi", max_tokens=10)
    payload = mock_client.post.call_args[1]["json"]
    assert payload["model"] == "mistral"


async def test_generate_sends_stream_false(mock_client: AsyncMock) -> None:
    with patch("httpx.AsyncClient", return_value=mock_client):
        await OllamaProvider().generate("hi", max_tokens=10)
    payload = mock_client.post.call_args[1]["json"]
    assert payload["stream"] is False


async def test_generate_no_auth_header_sent(mock_client: AsyncMock) -> None:
    """No API key or Authorization header must ever be sent to Ollama."""
    with patch("httpx.AsyncClient", return_value=mock_client):
        await OllamaProvider().generate("hi", max_tokens=10)
    call_kwargs = mock_client.post.call_args[1]
    headers = call_kwargs.get("headers", {})
    assert "Authorization" not in headers
    assert "api-key" not in headers
    assert "x-api-key" not in headers


async def test_generate_model_override(mock_client: AsyncMock) -> None:
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await OllamaProvider(model="llama3.1").generate(
            "hi", max_tokens=10, model="phi3"
        )
    assert result.model == "phi3"


async def test_generate_token_estimates_positive(mock_client: AsyncMock) -> None:
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await OllamaProvider().generate("x" * 400, max_tokens=200)
    assert result.input_tokens_estimate >= 1
    assert result.output_tokens_estimate >= 0


# ── generate() — prompt never logged ─────────────────────────────────────────


async def test_prompt_not_in_debug_logs(
    mock_client: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    sensitive = "SUPER_SECRET_PROMPT_CONTENT_DO_NOT_LOG"
    with (
        patch("httpx.AsyncClient", return_value=mock_client),
        caplog.at_level(
            logging.DEBUG,
            logger="app.ai_gateway.providers.ollama_provider",
        ),
    ):
        await OllamaProvider().generate(sensitive, max_tokens=10)
    for record in caplog.records:
        assert sensitive not in record.getMessage()


async def test_prompt_not_in_info_logs(
    mock_client: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    sensitive = "CONFIDENTIAL_PROMPT_12345"
    with (
        patch("httpx.AsyncClient", return_value=mock_client),
        caplog.at_level(
            logging.INFO,
            logger="app.ai_gateway.providers.ollama_provider",
        ),
    ):
        await OllamaProvider().generate(sensitive, max_tokens=10)
    for record in caplog.records:
        assert sensitive not in record.getMessage()


# ── generate() — error paths (safe failures) ─────────────────────────────────


async def test_connect_error_raises_unavailable() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            side_effect=httpx.ConnectError("refused")
        )
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(AIProviderUnavailableError, match="not reachable"):
            await OllamaProvider().generate("hello", max_tokens=10)


async def test_timeout_raises_unavailable() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        client.post.side_effect = httpx.TimeoutException("timeout")
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = client
        with pytest.raises(AIProviderUnavailableError, match="timed out"):
            await OllamaProvider().generate("hello", max_tokens=10)


async def test_http_status_error_raises_unavailable() -> None:
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
        with pytest.raises(AIProviderUnavailableError, match="HTTP 500"):
            await OllamaProvider().generate("hello", max_tokens=10)


# ── health_check() ────────────────────────────────────────────────────────────


async def test_health_check_true_when_reachable(mock_health_client: AsyncMock) -> None:
    with patch("httpx.AsyncClient", return_value=mock_health_client):
        assert await OllamaProvider().health_check() is True


async def test_health_check_false_on_connect_error() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        client.get.side_effect = httpx.ConnectError("refused")
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = client
        assert await OllamaProvider().health_check() is False


async def test_health_check_false_on_timeout() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        client.get.side_effect = httpx.TimeoutException("timeout")
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = client
        assert await OllamaProvider().health_check() is False


async def test_health_check_false_on_non_200() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        resp = MagicMock()
        resp.status_code = 503
        client = AsyncMock()
        client.get.return_value = resp
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = client
        assert await OllamaProvider().health_check() is False
