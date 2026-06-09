"""Unit tests for GeminiVisionProvider."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import VisionProviderUnavailableError
from app.vision.providers.base import VisionAnalysisResult
from app.vision.providers.gemini_vision import GeminiVisionProvider

_FAKE_KEY = "test-api-key-abc"
_FAKE_MODEL = "gemini-test-flash"

_VALID_GEMINI_RESPONSE = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "summary": "A cat sitting on a mat.",
                                "detected_objects": ["cat", "mat"],
                                "observations": ["The cat is orange.", "Indoors."],
                            }
                        )
                    }
                ],
                "role": "model",
            }
        }
    ],
    "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 40},
}


def _make_http_mock(status_code: int, json_data: dict[str, Any]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.text = json.dumps(json_data)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_cls = MagicMock(return_value=mock_client)
    return mock_cls


# ── Identity ──────────────────────────────────────────────────────────────────


def test_provider_name() -> None:
    p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
    assert p.provider_name == "gemini"


def test_model_name() -> None:
    p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
    assert p.model_name == _FAKE_MODEL


# ── Missing API key ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_raises_when_api_key_empty() -> None:
    p = GeminiVisionProvider(api_key="", model=_FAKE_MODEL)
    with pytest.raises(VisionProviderUnavailableError) as exc_info:
        await p.analyze(b"fake-image", prompt="")
    assert "GEMINI_API_KEY" in exc_info.value.message


_SETTINGS_PATH = "app.vision.providers.gemini_vision.settings.GEMINI_API_KEY"


@pytest.mark.asyncio
async def test_analyze_uses_settings_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_SETTINGS_PATH, "")
    p = GeminiVisionProvider()
    with pytest.raises(VisionProviderUnavailableError):
        await p.analyze(b"x", prompt="")


# ── Successful analysis ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_returns_vision_analysis_result() -> None:
    mock_cls = _make_http_mock(200, _VALID_GEMINI_RESPONSE)
    with patch("app.vision.providers.gemini_vision.httpx.AsyncClient", mock_cls):
        p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
        result = await p.analyze(b"fake-image", prompt="")
    assert isinstance(result, VisionAnalysisResult)


@pytest.mark.asyncio
async def test_analyze_content_is_json_string() -> None:
    mock_cls = _make_http_mock(200, _VALID_GEMINI_RESPONSE)
    with patch("app.vision.providers.gemini_vision.httpx.AsyncClient", mock_cls):
        p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
        result = await p.analyze(b"fake-image", prompt="")
    parsed = json.loads(result.content)
    assert "summary" in parsed
    assert "detected_objects" in parsed
    assert "observations" in parsed


@pytest.mark.asyncio
async def test_analyze_model_field_matches_provider() -> None:
    mock_cls = _make_http_mock(200, _VALID_GEMINI_RESPONSE)
    with patch("app.vision.providers.gemini_vision.httpx.AsyncClient", mock_cls):
        p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
        result = await p.analyze(b"fake-image", prompt="")
    assert result.model == _FAKE_MODEL


@pytest.mark.asyncio
async def test_analyze_token_counts_populated() -> None:
    mock_cls = _make_http_mock(200, _VALID_GEMINI_RESPONSE)
    with patch("app.vision.providers.gemini_vision.httpx.AsyncClient", mock_cls):
        p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
        result = await p.analyze(b"fake-image", prompt="")
    assert result.input_tokens == 100
    assert result.output_tokens == 40


# ── HTTP errors ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_raises_on_401() -> None:
    mock_cls = _make_http_mock(401, {"error": {"message": "API key invalid"}})
    with patch("app.vision.providers.gemini_vision.httpx.AsyncClient", mock_cls):
        p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
        with pytest.raises(VisionProviderUnavailableError) as exc_info:
            await p.analyze(b"img", prompt="")
    assert "401" in exc_info.value.message


@pytest.mark.asyncio
async def test_analyze_raises_on_500() -> None:
    mock_cls = _make_http_mock(500, {"error": "internal"})
    with patch("app.vision.providers.gemini_vision.httpx.AsyncClient", mock_cls):
        p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
        with pytest.raises(VisionProviderUnavailableError):
            await p.analyze(b"img", prompt="")


# ── Malformed response structure ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_raises_on_empty_candidates() -> None:
    bad_response: dict[str, Any] = {"candidates": []}
    mock_cls = _make_http_mock(200, bad_response)
    with patch("app.vision.providers.gemini_vision.httpx.AsyncClient", mock_cls):
        p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
        with pytest.raises(VisionProviderUnavailableError) as exc_info:
            await p.analyze(b"img", prompt="")
    assert "unexpected response structure" in exc_info.value.message


_NO_USAGE_CONTENT = '{"summary":"x","detected_objects":[],"observations":[]}'


@pytest.mark.asyncio
async def test_analyze_missing_usage_metadata_does_not_raise() -> None:
    response_no_usage = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": _NO_USAGE_CONTENT}],
                    "role": "model",
                }
            }
        ]
    }
    mock_cls = _make_http_mock(200, response_no_usage)
    with patch("app.vision.providers.gemini_vision.httpx.AsyncClient", mock_cls):
        p = GeminiVisionProvider(api_key=_FAKE_KEY, model=_FAKE_MODEL)
        result = await p.analyze(b"img", prompt="")
    assert result.input_tokens == 0
    assert result.output_tokens == 0
