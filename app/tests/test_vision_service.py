"""Unit tests for VisionService and processor utilities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ImageTooLargeError, UnsupportedFileTypeError
from app.core.security_context import SecurityContext
from app.vision.processor import (
    extract_pdf_text,
    is_image_file,
    is_pdf_file,
    validate_file,
)
from app.vision.providers.base import VisionAnalysisResult
from app.vision.service import VisionService


def _ctx(
    permissions: frozenset[str] | None = None,
) -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"admin"}),
        permissions=(
            permissions
            if permissions is not None
            else frozenset({"vision.analyze", "vision.extract", "rag.upload"})
        ),
    )


def _session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    return s


def _mock_provider(content: str = "Extracted text.") -> MagicMock:
    provider = MagicMock()
    provider.model_name = "qwen2.5-vl:7b"
    provider.analyze = AsyncMock(
        return_value=VisionAnalysisResult(
            content=content,
            model="qwen2.5-vl:7b",
            input_tokens=5,
            output_tokens=10,
        )
    )
    return provider


# ── Processor: validate_file ──────────────────────────────────────────────────


class TestValidateFile:
    def test_jpeg_accepted(self) -> None:
        mime = validate_file("photo.jpg", b"\xff\xd8\xff")
        assert mime == "image/jpeg"

    def test_png_accepted(self) -> None:
        mime = validate_file("image.png", b"\x89PNG")
        assert mime == "image/png"

    def test_webp_accepted(self) -> None:
        mime = validate_file("img.webp", b"RIFF")
        assert mime == "image/webp"

    def test_pdf_accepted(self) -> None:
        mime = validate_file("doc.pdf", b"%PDF-1.4")
        assert mime == "application/pdf"

    def test_unknown_extension_raises(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            validate_file("file.exe", b"MZ")

    def test_txt_extension_raises(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            validate_file("file.txt", b"hello")

    def test_file_too_large_raises(self) -> None:
        with pytest.raises(ImageTooLargeError):
            validate_file("img.png", b"x" * 10, max_bytes=5)

    def test_exact_limit_passes(self) -> None:
        mime = validate_file("img.png", b"x" * 5, max_bytes=5)
        assert mime == "image/png"


# ── Processor: helpers ────────────────────────────────────────────────────────


class TestProcessorHelpers:
    def test_is_image_jpeg(self) -> None:
        assert is_image_file("photo.jpg") is True

    def test_is_image_png(self) -> None:
        assert is_image_file("screen.png") is True

    def test_is_image_pdf_is_false(self) -> None:
        assert is_image_file("doc.pdf") is False

    def test_is_pdf_true(self) -> None:
        assert is_pdf_file("report.pdf") is True

    def test_is_pdf_image_false(self) -> None:
        assert is_pdf_file("image.png") is False


# ── Processor: extract_pdf_text ───────────────────────────────────────────────


class TestExtractPdfText:
    def test_extract_returns_list_of_strings(self) -> None:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page content here."
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page, mock_page]

        with patch("pypdf.PdfReader", return_value=mock_reader):
            pages = extract_pdf_text(b"%PDF-1.4 fake")

        assert len(pages) == 2
        assert pages[0] == "Page content here."

    def test_extract_empty_page_returns_empty_string(self) -> None:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("pypdf.PdfReader", return_value=mock_reader):
            pages = extract_pdf_text(b"%PDF")

        assert pages == [""]

    def test_extract_page_error_returns_empty_string(self) -> None:
        mock_page = MagicMock()
        mock_page.extract_text.side_effect = RuntimeError("parse fail")
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("pypdf.PdfReader", return_value=mock_reader):
            pages = extract_pdf_text(b"%PDF")

        assert pages == [""]


# ── VisionService.analyze_image ───────────────────────────────────────────────


class TestVisionServiceAnalyzeImage:
    @pytest.mark.asyncio
    async def test_analyze_returns_response(self) -> None:
        provider = _mock_provider("A dog in a park.")
        svc = VisionService(_session(), provider=provider)

        result = await svc.analyze_image(
            file_bytes=b"\xff\xd8\xff",
            filename="dog.jpg",
            ctx=_ctx(),
        )

        assert result.analysis == "A dog in a park."
        assert result.model == "qwen2.5-vl:7b"
        assert result.filename == "dog.jpg"
        assert result.file_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_analyze_calls_provider_with_prompt(self) -> None:
        provider = _mock_provider()
        svc = VisionService(_session(), provider=provider)

        await svc.analyze_image(
            file_bytes=b"\x89PNG",
            filename="chart.png",
            ctx=_ctx(),
            prompt="Describe the chart.",
        )

        provider.analyze.assert_awaited_once()
        _, call_kwargs = provider.analyze.call_args
        # positional: image_bytes, prompt
        args = provider.analyze.call_args.args
        assert args[1] == "Describe the chart."

    @pytest.mark.asyncio
    async def test_analyze_unsupported_type_raises(self) -> None:
        provider = _mock_provider()
        svc = VisionService(_session(), provider=provider)

        with pytest.raises(UnsupportedFileTypeError):
            await svc.analyze_image(
                file_bytes=b"data",
                filename="file.bmp",
                ctx=_ctx(),
            )

    @pytest.mark.asyncio
    async def test_analyze_too_large_raises(self) -> None:
        provider = _mock_provider()
        svc = VisionService(_session(), provider=provider)

        # Patch max size to 10 bytes
        with patch("app.vision.processor.settings") as mock_settings:
            mock_settings.VISION_MAX_IMAGE_SIZE_BYTES = 10
            with pytest.raises(ImageTooLargeError):
                await svc.analyze_image(
                    file_bytes=b"x" * 20,
                    filename="big.png",
                    ctx=_ctx(),
                )

    @pytest.mark.asyncio
    async def test_analyze_logs_vision_event(self) -> None:
        provider = _mock_provider()
        session = _session()
        svc = VisionService(session, provider=provider)

        await svc.analyze_image(
            file_bytes=b"\xff\xd8\xff",
            filename="photo.jpg",
            ctx=_ctx(),
        )

        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_analyze_index_into_rag_called(self) -> None:
        provider = _mock_provider("Some extracted text")
        svc = VisionService(_session(), provider=provider)

        with patch.object(
            svc,
            "_index_text",
            new=AsyncMock(return_value=(uuid4(), "indexed")),
        ) as mock_index:
            pid = uuid4()
            result = await svc.analyze_image(
                file_bytes=b"\x89PNG",
                filename="doc.png",
                ctx=_ctx(),
                project_id=pid,
                index_into_rag=True,
            )

        mock_index.assert_awaited_once()
        assert result.index_status == "indexed"

    @pytest.mark.asyncio
    async def test_analyze_no_rag_when_flag_false(self) -> None:
        provider = _mock_provider()
        svc = VisionService(_session(), provider=provider)

        with patch.object(svc, "_index_text", new=AsyncMock()) as mock_index:
            await svc.analyze_image(
                file_bytes=b"\x89PNG",
                filename="doc.png",
                ctx=_ctx(),
                project_id=uuid4(),
                index_into_rag=False,
            )

        mock_index.assert_not_awaited()


# ── VisionService.extract_pdf ─────────────────────────────────────────────────


class TestVisionServiceExtractPdf:
    @pytest.mark.asyncio
    async def test_extract_returns_pdf_response(self) -> None:
        provider = _mock_provider()
        svc = VisionService(_session(), provider=provider)

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Contract text page 1."
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page, mock_page]

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = await svc.extract_pdf(
                pdf_bytes=b"%PDF-1.4",
                filename="contract.pdf",
                ctx=_ctx(),
            )

        assert result.filename == "contract.pdf"
        assert result.page_count == 2
        assert len(result.text_pages) == 2
        assert result.total_chars > 0

    @pytest.mark.asyncio
    async def test_extract_non_pdf_raises(self) -> None:
        provider = _mock_provider()
        svc = VisionService(_session(), provider=provider)

        with pytest.raises(UnsupportedFileTypeError):
            await svc.extract_pdf(
                pdf_bytes=b"\x89PNG",
                filename="image.png",
                ctx=_ctx(),
            )

    @pytest.mark.asyncio
    async def test_extract_logs_event(self) -> None:
        provider = _mock_provider()
        session = _session()
        svc = VisionService(session, provider=provider)

        mock_reader = MagicMock()
        mock_reader.pages = []

        with patch("pypdf.PdfReader", return_value=mock_reader):
            await svc.extract_pdf(
                pdf_bytes=b"%PDF",
                filename="empty.pdf",
                ctx=_ctx(),
            )

        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_indexes_when_requested(self) -> None:
        provider = _mock_provider()
        svc = VisionService(_session(), provider=provider)

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page content."
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with (
            patch("pypdf.PdfReader", return_value=mock_reader),
            patch.object(
                svc,
                "_index_text",
                new=AsyncMock(return_value=(uuid4(), "indexed")),
            ) as mock_index,
        ):
            result = await svc.extract_pdf(
                pdf_bytes=b"%PDF",
                filename="report.pdf",
                ctx=_ctx(),
                project_id=uuid4(),
                index_into_rag=True,
            )

        mock_index.assert_awaited_once()
        assert result.index_status == "indexed"

    @pytest.mark.asyncio
    async def test_extract_skips_index_when_no_text(self) -> None:
        provider = _mock_provider()
        svc = VisionService(_session(), provider=provider)

        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with (
            patch("pypdf.PdfReader", return_value=mock_reader),
            patch.object(svc, "_index_text", new=AsyncMock()) as mock_index,
        ):
            await svc.extract_pdf(
                pdf_bytes=b"%PDF",
                filename="scanned.pdf",
                ctx=_ctx(),
                project_id=uuid4(),
                index_into_rag=True,
            )

        mock_index.assert_not_awaited()
