"""Unit tests for VisionAnalyzeTool agent tool."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agent.tools.vision_analyze import VisionAnalyzeTool
from app.core.security_context import SecurityContext
from app.vision.schemas import VisionAnalyzeResponse


def _ctx(
    permissions: frozenset[str] | None = None,
) -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"admin"}),
        permissions=(
            permissions if permissions is not None else frozenset({"vision.analyze"})
        ),
    )


def _session() -> AsyncMock:
    return AsyncMock()


def _b64(data: bytes = b"\x89PNG fake image") -> str:
    return base64.b64encode(data).decode("ascii")


def _analyze_response(text: str = "A dog on a beach.") -> VisionAnalyzeResponse:
    return VisionAnalyzeResponse(
        analysis=text,
        summary=text,
        provider="ollama",
        model="qwen2.5-vl:7b",
        filename="photo.png",
        file_type="image/png",
    )


# ── Tool definition ───────────────────────────────────────────────────────────


class TestToolDefinition:
    def test_name_is_vision_analyze(self) -> None:
        tool = VisionAnalyzeTool()
        assert tool.definition.name == "vision_analyze"

    def test_requires_vision_analyze_permission(self) -> None:
        tool = VisionAnalyzeTool()
        assert tool.definition.required_permission == "vision.analyze"

    def test_has_image_base64_parameter(self) -> None:
        tool = VisionAnalyzeTool()
        param_names = [p.name for p in tool.definition.parameters]
        assert "image_base64" in param_names

    def test_has_filename_parameter(self) -> None:
        tool = VisionAnalyzeTool()
        param_names = [p.name for p in tool.definition.parameters]
        assert "filename" in param_names

    def test_has_prompt_parameter(self) -> None:
        tool = VisionAnalyzeTool()
        param_names = [p.name for p in tool.definition.parameters]
        assert "prompt" in param_names

    def test_image_base64_is_required(self) -> None:
        tool = VisionAnalyzeTool()
        param = next(p for p in tool.definition.parameters if p.name == "image_base64")
        assert param.required is True

    def test_filename_is_required(self) -> None:
        tool = VisionAnalyzeTool()
        param = next(p for p in tool.definition.parameters if p.name == "filename")
        assert param.required is True

    def test_prompt_is_optional(self) -> None:
        tool = VisionAnalyzeTool()
        param = next(p for p in tool.definition.parameters if p.name == "prompt")
        assert param.required is False


# ── Successful execution ──────────────────────────────────────────────────────


class TestVisionToolSuccess:
    @pytest.mark.asyncio
    async def test_returns_success_result(self) -> None:
        tool = VisionAnalyzeTool()
        mock_svc = MagicMock()
        mock_svc.analyze_image = AsyncMock(return_value=_analyze_response())

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            result = await tool.execute(
                params={
                    "image_base64": _b64(),
                    "filename": "photo.png",
                    "prompt": "Describe this image.",
                },
                ctx=_ctx(),
                session=_session(),
            )

        assert result.success is True
        assert result.data is not None
        assert result.data["analysis"] == "A dog on a beach."

    @pytest.mark.asyncio
    async def test_result_contains_model(self) -> None:
        tool = VisionAnalyzeTool()
        mock_svc = MagicMock()
        mock_svc.analyze_image = AsyncMock(return_value=_analyze_response())

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            result = await tool.execute(
                params={
                    "image_base64": _b64(),
                    "filename": "shot.png",
                },
                ctx=_ctx(),
                session=_session(),
            )

        assert result.data["model"] == "qwen2.5-vl:7b"

    @pytest.mark.asyncio
    async def test_result_contains_filename(self) -> None:
        tool = VisionAnalyzeTool()
        mock_svc = MagicMock()
        resp = _analyze_response()
        mock_svc.analyze_image = AsyncMock(return_value=resp)

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            result = await tool.execute(
                params={"image_base64": _b64(), "filename": "photo.png"},
                ctx=_ctx(),
                session=_session(),
            )

        assert result.data["filename"] == "photo.png"

    @pytest.mark.asyncio
    async def test_passes_prompt_to_service(self) -> None:
        tool = VisionAnalyzeTool()
        mock_svc = MagicMock()
        mock_svc.analyze_image = AsyncMock(return_value=_analyze_response())

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            await tool.execute(
                params={
                    "image_base64": _b64(),
                    "filename": "photo.png",
                    "prompt": "Extract all text.",
                },
                ctx=_ctx(),
                session=_session(),
            )

        _, call_kwargs = mock_svc.analyze_image.call_args
        assert call_kwargs.get("prompt") == "Extract all text."


# ── Input validation ──────────────────────────────────────────────────────────


class TestVisionToolInputValidation:
    @pytest.mark.asyncio
    async def test_missing_image_base64_returns_failure(self) -> None:
        tool = VisionAnalyzeTool()
        result = await tool.execute(
            params={"filename": "photo.png"},
            ctx=_ctx(),
            session=_session(),
        )
        assert result.success is False
        assert "image_base64" in (result.error or "")

    @pytest.mark.asyncio
    async def test_invalid_base64_returns_failure(self) -> None:
        tool = VisionAnalyzeTool()
        result = await tool.execute(
            params={"image_base64": "!!not valid base64!!", "filename": "photo.png"},
            ctx=_ctx(),
            session=_session(),
        )
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_empty_image_base64_returns_failure(self) -> None:
        tool = VisionAnalyzeTool()
        result = await tool.execute(
            params={"image_base64": "", "filename": "photo.png"},
            ctx=_ctx(),
            session=_session(),
        )
        assert result.success is False


# ── Permission checks ─────────────────────────────────────────────────────────


class TestVisionToolPermissions:
    @pytest.mark.asyncio
    async def test_missing_permission_returns_failure(self) -> None:
        tool = VisionAnalyzeTool()
        no_perm_ctx = _ctx(frozenset())

        result = await tool.execute(
            params={"image_base64": _b64(), "filename": "photo.png"},
            ctx=no_perm_ctx,
            session=_session(),
        )

        assert result.success is False
        assert "vision.analyze" in (result.error or "")


# ── Error handling ────────────────────────────────────────────────────────────


class TestVisionToolErrorHandling:
    @pytest.mark.asyncio
    async def test_unsupported_type_returns_failure(self) -> None:
        from app.core.exceptions import UnsupportedFileTypeError

        tool = VisionAnalyzeTool()
        mock_svc = MagicMock()
        mock_svc.analyze_image = AsyncMock(
            side_effect=UnsupportedFileTypeError("Unsupported file type '.exe'")
        )

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            result = await tool.execute(
                params={"image_base64": _b64(), "filename": "malware.exe"},
                ctx=_ctx(),
                session=_session(),
            )

        assert result.success is False
        assert "Unsupported" in (result.error or "")

    @pytest.mark.asyncio
    async def test_too_large_returns_failure(self) -> None:
        from app.core.exceptions import ImageTooLargeError

        tool = VisionAnalyzeTool()
        mock_svc = MagicMock()
        mock_svc.analyze_image = AsyncMock(
            side_effect=ImageTooLargeError("Image exceeds maximum size")
        )

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            result = await tool.execute(
                params={"image_base64": _b64(), "filename": "huge.png"},
                ctx=_ctx(),
                session=_session(),
            )

        assert result.success is False
        assert "large" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_provider_unavailable_returns_failure(self) -> None:
        from app.core.exceptions import VisionProviderUnavailableError

        tool = VisionAnalyzeTool()
        mock_svc = MagicMock()
        mock_svc.analyze_image = AsyncMock(
            side_effect=VisionProviderUnavailableError("Ollama is unreachable")
        )

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            result = await tool.execute(
                params={"image_base64": _b64(), "filename": "photo.jpg"},
                ctx=_ctx(),
                session=_session(),
            )

        assert result.success is False
        assert "unavailable" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_failure(self) -> None:
        tool = VisionAnalyzeTool()
        mock_svc = MagicMock()
        mock_svc.analyze_image = AsyncMock(
            side_effect=RuntimeError("database exploded")
        )

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            result = await tool.execute(
                params={"image_base64": _b64(), "filename": "photo.png"},
                ctx=_ctx(),
                session=_session(),
            )

        assert result.success is False
        assert result.error is not None
