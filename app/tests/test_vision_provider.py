"""Unit tests for the Ollama vision provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import VisionProviderUnavailableError
from app.vision.providers.base import VisionAnalysisResult
from app.vision.providers.ollama_vision import OllamaVisionProvider


def _make_provider(model: str = "qwen2.5-vl:7b") -> OllamaVisionProvider:
    return OllamaVisionProvider(
        base_url="http://localhost:11434",
        model=model,
        timeout=10.0,
    )


def _mock_response(content: str = "Image shows a cat.") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "message": {"content": content},
        "usage": {"prompt_eval_count": 10, "eval_count": 20},
    }
    return resp


# ── Provider identity ─────────────────────────────────────────────────────────


class TestProviderIdentity:
    def test_provider_name(self) -> None:
        assert _make_provider().provider_name == "ollama"

    def test_model_name_from_arg(self) -> None:
        p = _make_provider("llama3.2-vision:11b")
        assert p.model_name == "llama3.2-vision:11b"

    def test_model_name_default(self) -> None:
        from app.core.config import settings

        p = OllamaVisionProvider()
        assert p.model_name == settings.VISION_MODEL


# ── Successful analysis ───────────────────────────────────────────────────────


class TestAnalyzeSuccess:
    @pytest.mark.asyncio
    async def test_returns_vision_analysis_result(self) -> None:
        provider = _make_provider()
        mock_resp = _mock_response("A fluffy cat sitting on a mat.")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client

            result = await provider.analyze(b"\xff\xd8\xff", "Describe this image.")

        assert isinstance(result, VisionAnalysisResult)
        assert "cat" in result.content

    @pytest.mark.asyncio
    async def test_result_contains_model_name(self) -> None:
        provider = _make_provider("qwen2.5-vl:7b")
        mock_resp = _mock_response("Some content.")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client

            result = await provider.analyze(b"\x89PNG", "Analyze.")

        assert result.model == "qwen2.5-vl:7b"

    @pytest.mark.asyncio
    async def test_token_counts_populated(self) -> None:
        provider = _make_provider()
        mock_resp = _mock_response("Output text.")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client

            result = await provider.analyze(b"img", "Prompt.")

        assert result.input_tokens == 10
        assert result.output_tokens == 20

    @pytest.mark.asyncio
    async def test_payload_uses_base64_image(self) -> None:
        import base64

        provider = _make_provider()
        image_bytes = b"FAKE_IMAGE_DATA"
        expected_b64 = base64.b64encode(image_bytes).decode("ascii")
        mock_resp = _mock_response("ok")

        captured_payload: dict = {}

        async def capture_post(url: str, json: dict) -> MagicMock:
            captured_payload.update(json)
            return mock_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = capture_post
            mock_cls.return_value = mock_client

            await provider.analyze(image_bytes, "Describe.")

        images = captured_payload["messages"][0]["images"]
        assert images[0] == expected_b64

    @pytest.mark.asyncio
    async def test_payload_uses_configured_model(self) -> None:
        provider = _make_provider("llama3.2-vision:11b")
        mock_resp = _mock_response("ok")
        captured: dict = {}

        async def capture_post(url: str, json: dict) -> MagicMock:
            captured.update(json)
            return mock_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = capture_post
            mock_cls.return_value = mock_client

            await provider.analyze(b"img", "Describe.")

        assert captured["model"] == "llama3.2-vision:11b"

    @pytest.mark.asyncio
    async def test_low_temperature_in_options(self) -> None:
        provider = _make_provider()
        mock_resp = _mock_response("ok")
        captured: dict = {}

        async def capture_post(url: str, json: dict) -> MagicMock:
            captured.update(json)
            return mock_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = capture_post
            mock_cls.return_value = mock_client

            await provider.analyze(b"img", "Describe.")

        assert captured.get("options", {}).get("temperature", 1.0) <= 0.2


# ── Error handling ────────────────────────────────────────────────────────────


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_connect_error_raises_unavailable(self) -> None:
        import httpx

        provider = _make_provider()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_cls.return_value = mock_client

            with pytest.raises(VisionProviderUnavailableError):
                await provider.analyze(b"img", "Describe.")

    @pytest.mark.asyncio
    async def test_timeout_raises_unavailable(self) -> None:
        import httpx

        provider = _make_provider()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("timed out")
            )
            mock_cls.return_value = mock_client

            with pytest.raises(VisionProviderUnavailableError):
                await provider.analyze(b"img", "Describe.")

    @pytest.mark.asyncio
    async def test_http_error_raises_unavailable(self) -> None:
        import httpx

        provider = _make_provider()
        bad_resp = MagicMock()
        bad_resp.status_code = 500

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "server error",
                    request=MagicMock(),
                    response=bad_resp,
                )
            )
            mock_cls.return_value = mock_client

            with pytest.raises(VisionProviderUnavailableError):
                await provider.analyze(b"img", "Describe.")
