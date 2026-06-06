"""Image and PDF validation / text-extraction utilities.

Security invariants:
- File bytes are NEVER logged — only size and type metadata.
- PDF text extraction uses pypdf (pure Python, no system dependencies).
- Unsupported types are rejected early with a clear error.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ImageTooLargeError, UnsupportedFileTypeError

logger = logging.getLogger(__name__)

_SUPPORTED_IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".webp"}
)
_SUPPORTED_PDF_SUFFIX: str = ".pdf"
_SUPPORTED_ALL: frozenset[str] = _SUPPORTED_IMAGE_SUFFIXES | {_SUPPORTED_PDF_SUFFIX}

_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def validate_file(
    filename: str,
    file_bytes: bytes,
    *,
    max_bytes: int | None = None,
) -> str:
    """Validate file type and size; return the MIME type string.

    Raises
    ------
    UnsupportedFileTypeError
        If the file extension is not in the supported set.
    ImageTooLargeError
        If the file exceeds the configured size limit.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_ALL:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. "
            f"Accepted: {', '.join(sorted(_SUPPORTED_ALL))}"
        )

    limit = max_bytes if max_bytes is not None else settings.VISION_MAX_IMAGE_SIZE_BYTES
    if len(file_bytes) > limit:
        mb_actual = len(file_bytes) / (1024 * 1024)
        mb_limit = limit // (1024 * 1024)
        raise ImageTooLargeError(
            f"File is {mb_actual:.1f} MB; maximum allowed is {mb_limit} MB"
        )

    return _MIME_MAP.get(suffix, "application/octet-stream")


def extract_pdf_text(pdf_bytes: bytes) -> list[str]:
    """Extract plain text from each page of a PDF using pypdf.

    Returns a list where index i is the text of page i+1.
    Pages with no extractable text (e.g. scanned images) return an empty string.
    """
    try:
        import pypdf
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required for PDF extraction. Install with: pip install pypdf"
        ) from exc

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
            pages.append(text.strip())
        except Exception:
            logger.warning("vision.pdf.page_error page_index=%d", i)
            pages.append("")

    logger.debug(
        "vision.pdf.extracted pages=%d total_chars=%d",
        len(pages),
        sum(len(p) for p in pages),
    )
    return pages


def is_image_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in _SUPPORTED_IMAGE_SUFFIXES


def is_pdf_file(filename: str) -> bool:
    return Path(filename).suffix.lower() == _SUPPORTED_PDF_SUFFIX
