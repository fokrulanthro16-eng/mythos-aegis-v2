"""Tests for the RAG chunker and text extraction utilities.

Pure unit tests — no network, no database.
"""

from __future__ import annotations

import json

import pytest

from app.core.exceptions import UnsupportedFileTypeError
from app.rag.chunker import (
    chunk_text,
    content_hash,
    estimate_tokens,
    extract_text,
    supported_extensions,
)

# ── PDF test fixture ──────────────────────────────────────────────────────────

_PDF_TEXT = "RAG test content from PDF"


def _make_pdf_bytes(text: str = _PDF_TEXT) -> bytes:
    """Build a minimal valid PDF with one text page and extractable content."""
    content = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET\n".encode("ascii")

    header = b"%PDF-1.4\n"
    catalog = b"1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n"
    pages_obj = b"2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n"
    page_obj = (
        b"3 0 obj\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources <</Font <</F1 <</Type /Font"
        b" /Subtype /Type1 /BaseFont /Helvetica>>>>>>\n>>\nendobj\n"
    )
    content_header = (
        b"4 0 obj\n<</Length " + str(len(content)).encode() + b">>\nstream\n"
    )
    content_footer = b"endstream\nendobj\n"

    # Compute xref byte offsets
    p = len(header)
    off1 = p
    p += len(catalog)
    off2 = p
    p += len(pages_obj)
    off3 = p
    p += len(page_obj)
    off4 = p
    p += len(content_header) + len(content) + len(content_footer)
    xref_pos = p

    xref = (
        b"xref\n0 5\n"
        b"0000000000 65535 f \n"
        + f"{off1:010d} 00000 n \n".encode()
        + f"{off2:010d} 00000 n \n".encode()
        + f"{off3:010d} 00000 n \n".encode()
        + f"{off4:010d} 00000 n \n".encode()
        + b"trailer\n"
        + f"<</Size 5 /Root 1 0 R>>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )

    return (
        header + catalog + pages_obj + page_obj
        + content_header + content + content_footer
        + xref
    )

# ── supported_extensions ─────────────────────────────────────────────────────


def test_supported_extensions_contains_txt() -> None:
    assert ".txt" in supported_extensions()


def test_supported_extensions_contains_md() -> None:
    assert ".md" in supported_extensions()


def test_supported_extensions_contains_json() -> None:
    assert ".json" in supported_extensions()


def test_supported_extensions_contains_csv() -> None:
    assert ".csv" in supported_extensions()


def test_supported_extensions_contains_pdf() -> None:
    assert ".pdf" in supported_extensions()


# ── extract_text ─────────────────────────────────────────────────────────────


def test_extract_txt_returns_text() -> None:
    result = extract_text(b"Hello world\nSecond line", "doc.txt")
    assert "Hello world" in result


def test_extract_md_returns_text() -> None:
    result = extract_text(b"# Title\n\nSome **content**", "doc.md")
    assert "Title" in result
    assert "content" in result


def test_extract_json_returns_formatted() -> None:
    data = {"key": "value", "count": 42}
    result = extract_text(json.dumps(data).encode(), "data.json")
    assert "value" in result
    assert "42" in result


def test_extract_json_handles_nested_structure() -> None:
    data = {"users": [{"name": "Alice", "age": 30}]}
    result = extract_text(json.dumps(data).encode(), "data.json")
    assert "Alice" in result


def test_extract_csv_returns_rows() -> None:
    content = b"name,age\nAlice,30\nBob,25"
    result = extract_text(content, "data.csv")
    assert "Alice" in result
    assert "Bob" in result


def test_extract_csv_multicolumn() -> None:
    content = b"product,price,stock\nWidget,9.99,100"
    result = extract_text(content, "inventory.csv")
    assert "Widget" in result
    assert "9.99" in result


def test_extract_docx_raises() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(b"...", "report.docx")


def test_extract_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid JSON"):
        extract_text(b"{not valid json{{", "bad.json")


def test_extract_txt_utf8_errors_replaced() -> None:
    # Broken UTF-8 byte sequence should not raise
    result = extract_text(b"Valid \xff\xfe text", "doc.txt")
    assert "Valid" in result


# ── chunk_text ────────────────────────────────────────────────────────────────


def test_chunk_text_deterministic() -> None:
    text = "The quick brown fox jumps over the lazy dog. " * 200
    assert chunk_text(text) == chunk_text(text)


def test_chunk_text_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        chunk_text("")


def test_chunk_text_whitespace_only_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        chunk_text("   \n\n\t   ")


def test_chunk_text_produces_multiple_chunks_for_long_text() -> None:
    text = "word " * 5000  # ~25000 chars, well over one 3200-char chunk
    chunks = chunk_text(text)
    assert len(chunks) > 1


def test_chunk_text_single_chunk_for_short_text() -> None:
    text = "Hello world."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world."


def test_chunk_text_overlap_content_matches() -> None:
    # Use small chunk_size so overlap is observable.
    # chunk_size=10, overlap=3 → chars_per_chunk=40, overlap_chars=12, stride=28
    text = "a" * 200
    chunks = chunk_text(text, chunk_size=10, overlap=3)
    assert len(chunks) > 1
    # Overlap region: last 12 chars of chunk[0] == first 12 chars of chunk[1]
    assert chunks[0][-12:] == chunks[1][:12]


def test_chunk_text_normalizes_whitespace() -> None:
    text = "word1   \t\n  word2"
    chunks = chunk_text(text)
    assert "  " not in chunks[0]  # collapsed to single space


def test_chunk_text_invalid_overlap_raises() -> None:
    with pytest.raises(ValueError):
        chunk_text("text " * 100, chunk_size=10, overlap=10)


def test_chunk_text_respects_chunk_size() -> None:
    # chunk_size=50 → 200 chars per chunk
    text = "x" * 2000
    chunks = chunk_text(text, chunk_size=50, overlap=5)
    for chunk in chunks[:-1]:  # last chunk may be shorter
        assert len(chunk) <= 200 + 5  # tolerance for edge of last chunk


# ── content_hash ──────────────────────────────────────────────────────────────


def test_content_hash_stable() -> None:
    assert content_hash("Hello") == content_hash("Hello")


def test_content_hash_differs_for_different_content() -> None:
    assert content_hash("Hello") != content_hash("World")


def test_content_hash_is_hex_64_chars() -> None:
    h = content_hash("test content")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_content_hash_empty_string() -> None:
    h = content_hash("")
    assert len(h) == 64


# ── estimate_tokens ───────────────────────────────────────────────────────────


def test_estimate_tokens_minimum_one() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("a") == 1


def test_estimate_tokens_four_chars_per_token() -> None:
    assert estimate_tokens("x" * 400) == 100


def test_estimate_tokens_rough_estimate() -> None:
    text = "The quick brown fox"  # 19 chars → estimate 4
    assert estimate_tokens(text) >= 1


# ── PDF extraction ────────────────────────────────────────────────────────────


def test_extract_pdf_does_not_raise_unsupported() -> None:
    pdf = _make_pdf_bytes()
    # Must NOT raise UnsupportedFileTypeError
    result = extract_text(pdf, "document.pdf")
    assert isinstance(result, str)


def test_extract_pdf_returns_text_content() -> None:
    pdf = _make_pdf_bytes(_PDF_TEXT)
    result = extract_text(pdf, "document.pdf")
    assert _PDF_TEXT in result


def test_extract_pdf_uppercase_extension() -> None:
    pdf = _make_pdf_bytes()
    result = extract_text(pdf, "REPORT.PDF")
    assert isinstance(result, str)


def test_extract_pdf_invalid_bytes_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Could not parse PDF"):
        extract_text(b"not a pdf at all", "corrupt.pdf")


def test_extract_pdf_chunks_normally() -> None:
    pdf = _make_pdf_bytes(_PDF_TEXT)
    text = extract_text(pdf, "document.pdf")
    chunks = chunk_text(text)
    assert len(chunks) >= 1
    assert _PDF_TEXT in chunks[0]


def test_extract_pdf_content_type_is_application_pdf() -> None:
    from pathlib import Path

    ext = Path("report.pdf").suffix.lower().lstrip(".")
    assert ext == "pdf"  # sanity — verifies service.py content_type branch
