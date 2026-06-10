"""Deterministic text extraction and chunking.

Security invariant: document content is never written to any log.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
from pathlib import Path

from app.core.exceptions import UnsupportedFileTypeError

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = frozenset({".txt", ".md", ".json", ".csv", ".pdf"})

# 4 characters ≈ 1 token (rough estimate consistent with AI Gateway)
_CHARS_PER_TOKEN = 4


def supported_extensions() -> frozenset[str]:
    return _SUPPORTED_EXTENSIONS


def extract_text(content: bytes, filename: str) -> str:
    """Convert raw file bytes to a plain-text string.

    Raises ``UnsupportedFileTypeError`` for unsupported extensions.
    Raises ``ValueError`` for malformed content (e.g. invalid JSON).
    Content is never written to any log.
    """
    ext = Path(filename).suffix.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext}'. Supported: {sorted(_SUPPORTED_EXTENSIONS)}"
        )

    if ext in (".txt", ".md"):
        return content.decode("utf-8", errors="replace")

    if ext == ".json":
        try:
            data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON content: {exc}") from exc
        return json.dumps(data, indent=2, ensure_ascii=False)

    if ext == ".pdf":
        try:
            import pypdf
        except ImportError as exc:
            raise RuntimeError(
                "pypdf is required for PDF text extraction. "
                "Install with: pip install pypdf"
            ) from exc

        try:
            pdf_reader = pypdf.PdfReader(io.BytesIO(content))
        except Exception as exc:
            raise ValueError(f"Could not parse PDF: {exc}") from exc

        pages: list[str] = []
        for i, page in enumerate(pdf_reader.pages):
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                logger.warning("rag.chunker.pdf_page_error page_index=%d", i)
                pages.append("")

        return "\n\n".join(p for p in pages if p.strip())

    # .csv
    text = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    return "\n".join(", ".join(row) for row in reader)


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """Split *text* into overlapping chunks.

    Args:
        text:       Input text (after extraction).
        chunk_size: Target chunk size in token estimates (1 token ≈ 4 chars).
        overlap:    Overlap between adjacent chunks in token estimates.

    Returns a list of non-empty string chunks.
    Content is never logged.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chars_per_chunk = chunk_size * _CHARS_PER_TOKEN
    overlap_chars = overlap * _CHARS_PER_TOKEN
    stride = chars_per_chunk - overlap_chars

    # Normalize: collapse whitespace runs to single spaces.
    normalized = re.sub(r"\s+", " ", text).strip()

    if not normalized:
        raise ValueError("Document content is empty after normalization")

    chunks: list[str] = []
    pos = 0
    while pos < len(normalized):
        chunk = normalized[pos : pos + chars_per_chunk]
        if chunk.strip():
            chunks.append(chunk)
        pos += stride

    return chunks


def content_hash(text: str) -> str:
    """Return a stable SHA-256 hex digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    return max(1, len(text) // _CHARS_PER_TOKEN)
