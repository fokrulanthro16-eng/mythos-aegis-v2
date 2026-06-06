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

# ── supported_extensions ─────────────────────────────────────────────────────


def test_supported_extensions_contains_txt() -> None:
    assert ".txt" in supported_extensions()


def test_supported_extensions_contains_md() -> None:
    assert ".md" in supported_extensions()


def test_supported_extensions_contains_json() -> None:
    assert ".json" in supported_extensions()


def test_supported_extensions_contains_csv() -> None:
    assert ".csv" in supported_extensions()


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


def test_extract_unsupported_raises() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(b"%PDF", "document.pdf")


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
