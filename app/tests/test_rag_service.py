"""Tests for the RAG service layer.

All Ollama HTTP calls and DB operations are mocked.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai_gateway.providers.base import GenerateResult
from app.core.exceptions import (
    AIProviderUnavailableError,
    EmbeddingError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.core.result import Failure, Success
from app.core.security_context import SecurityContext
from app.db.models.document import DocumentStatus
from app.db.models.document_chunk import DocumentChunk
from app.rag.schemas import AskRequest, SearchRequest
from app.rag.service import RAGService

# ── Shared fixtures ───────────────────────────────────────────────────────────


def _ctx(
    permissions: frozenset[str] | None = None,
) -> SecurityContext:
    if permissions is None:
        permissions = frozenset({"rag.upload", "rag.search", "rag.ask"})
    tid = uuid4()
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=tid,
        roles=frozenset({"user"}),
        permissions=permissions,
    )


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()  # SQLAlchemy session.add is synchronous
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = None
    db_result.scalars.return_value.all.return_value = []
    db_result.scalar.return_value = 0
    db_result.all.return_value = []
    session.execute.return_value = db_result
    return session


def _make_embedding_provider(dim: int = 768) -> MagicMock:
    provider = MagicMock()
    provider.embed = AsyncMock(return_value=[0.1] * dim)
    provider.embed_batch = AsyncMock(return_value=[[0.1] * dim])
    return provider


def _make_answer_provider(output: str = "The answer is 42.") -> MagicMock:
    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=GenerateResult(
            output=output,
            input_tokens_estimate=20,
            output_tokens_estimate=10,
            model="llama3.1",
            provider="ollama",
        )
    )
    return provider


def _make_chunk(
    tenant_id: object,
    project_id: object,
    doc_id: object,
    idx: int = 0,
) -> DocumentChunk:
    chunk = DocumentChunk(
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=doc_id,
        chunk_index=idx,
        content="Relevant policy content about vacations.",
        content_hash=f"hash{idx}",
        token_estimate=10,
        citation_label=f"policy#chunk-{idx}",
    )
    return chunk


# ── upload_document ───────────────────────────────────────────────────────────


async def test_upload_missing_permission_returns_failure() -> None:
    ctx = _ctx(frozenset())  # no permissions
    session = _make_session()
    svc = RAGService(session, _make_embedding_provider())
    result = await svc.upload_document(b"hello", "test.txt", uuid4(), ctx)
    assert isinstance(result, Failure)
    assert "rag.upload" in result.message


async def test_upload_too_large_returns_failure() -> None:
    ctx = _ctx()
    session = _make_session()
    svc = RAGService(session, _make_embedding_provider())
    huge = b"x" * (11 * 1024 * 1024)  # 11 MB > 10 MB limit
    result = await svc.upload_document(huge, "big.txt", uuid4(), ctx)
    assert isinstance(result, Failure)
    assert isinstance(result.error, FileTooLargeError)


async def test_upload_unsupported_type_returns_failure() -> None:
    ctx = _ctx()
    session = _make_session()
    svc = RAGService(session, _make_embedding_provider())
    result = await svc.upload_document(b"...", "report.docx", uuid4(), ctx)
    assert isinstance(result, Failure)
    assert isinstance(result.error, UnsupportedFileTypeError)


async def test_upload_success_returns_document_id() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    # Return one embedding per input chunk (count is determined at runtime)
    embedder.embed_batch = AsyncMock(
        side_effect=lambda texts: [[0.1] * 768 for _ in texts]
    )
    svc = RAGService(session, embedder)
    result = await svc.upload_document(
        b"Hello world. " * 500, "policy.txt", uuid4(), ctx
    )
    assert isinstance(result, Success)
    assert result.value.filename == "policy.txt"
    assert result.value.status == DocumentStatus.INDEXED
    assert result.value.chunk_count >= 1


async def test_upload_marks_failed_on_embedding_error() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    embedder.embed_batch = AsyncMock(side_effect=EmbeddingError("Ollama down"))
    svc = RAGService(session, embedder)
    result = await svc.upload_document(b"Some text content.", "doc.txt", uuid4(), ctx)
    assert isinstance(result, Failure)
    assert isinstance(result.error, EmbeddingError)


async def test_upload_does_not_log_content(caplog: pytest.LogCaptureFixture) -> None:
    sensitive = "PRIVATE_DOCUMENT_CONTENT_DO_NOT_LOG_XYZ"
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    embedder.embed_batch = AsyncMock(return_value=[[0.1] * 768])
    svc = RAGService(session, embedder)
    with caplog.at_level(logging.DEBUG, logger="app.rag"):
        await svc.upload_document(sensitive.encode() * 10, "doc.txt", uuid4(), ctx)
    for record in caplog.records:
        assert sensitive not in record.getMessage()


# ── search ────────────────────────────────────────────────────────────────────


async def test_search_missing_permission_returns_failure() -> None:
    ctx = _ctx(frozenset())
    session = _make_session()
    svc = RAGService(session, _make_embedding_provider())
    req = SearchRequest(project_id=uuid4(), query="What is the policy?")
    result = await svc.search(req, ctx)
    assert isinstance(result, Failure)
    assert "rag.search" in result.message


async def test_search_returns_empty_when_no_chunks() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    svc = RAGService(session, embedder)
    # Patch the chunk repo to return empty
    svc._chunks.search_similar = AsyncMock(return_value=[])  # type: ignore[method-assign]
    req = SearchRequest(project_id=uuid4(), query="vacation policy")
    result = await svc.search(req, ctx)
    assert isinstance(result, Success)
    assert result.value.results == []


async def test_search_enforces_tenant_isolation() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    svc = RAGService(session, embedder)
    captured_kwargs: dict[str, object] = {}

    async def mock_search(**kwargs: object) -> list[object]:
        captured_kwargs.update(kwargs)
        return []

    svc._chunks.search_similar = mock_search  # type: ignore[assignment]
    req = SearchRequest(project_id=uuid4(), query="test")
    await svc.search(req, ctx)
    # The tenant_id used must be from ctx, not from the request body
    assert captured_kwargs["tenant_id"] == ctx.tenant_id


async def test_search_enforces_project_isolation() -> None:
    project_id = uuid4()
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    svc = RAGService(session, embedder)
    captured_kwargs: dict[str, object] = {}

    async def mock_search(**kwargs: object) -> list[object]:
        captured_kwargs.update(kwargs)
        return []

    svc._chunks.search_similar = mock_search  # type: ignore[assignment]
    req = SearchRequest(project_id=project_id, query="test")
    await svc.search(req, ctx)
    assert captured_kwargs["project_id"] == project_id


async def test_search_results_have_no_raw_embeddings() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    svc = RAGService(session, embedder)

    doc_id = uuid4()
    chunk = _make_chunk(ctx.tenant_id, uuid4(), doc_id)
    chunk.embedding = [0.1] * 768  # set on the ORM object

    svc._chunks.search_similar = AsyncMock(  # type: ignore[method-assign]
        return_value=[(chunk, "policy.txt")]
    )
    req = SearchRequest(project_id=uuid4(), query="vacations")
    result = await svc.search(req, ctx)
    assert isinstance(result, Success)
    for item in result.value.results:
        # ChunkResult has no 'embedding' field
        assert not hasattr(item, "embedding")


async def test_search_excerpt_max_500_chars() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    svc = RAGService(session, embedder)

    doc_id = uuid4()
    chunk = _make_chunk(ctx.tenant_id, uuid4(), doc_id)
    chunk.content = "x" * 2000  # content longer than excerpt limit

    svc._chunks.search_similar = AsyncMock(  # type: ignore[method-assign]
        return_value=[(chunk, "policy.txt")]
    )
    req = SearchRequest(project_id=uuid4(), query="test")
    result = await svc.search(req, ctx)
    assert isinstance(result, Success)
    assert len(result.value.results[0].excerpt) <= 500


async def test_search_embedding_error_returns_failure() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    embedder.embed = AsyncMock(side_effect=EmbeddingError("Ollama down"))
    svc = RAGService(session, embedder)
    req = SearchRequest(project_id=uuid4(), query="test")
    result = await svc.search(req, ctx)
    assert isinstance(result, Failure)


# ── ask ───────────────────────────────────────────────────────────────────────


async def test_ask_missing_permission_returns_failure() -> None:
    ctx = _ctx(frozenset())
    session = _make_session()
    svc = RAGService(session, _make_embedding_provider())
    req = AskRequest(project_id=uuid4(), question="What is the policy?")
    result = await svc.ask(req, ctx)
    assert isinstance(result, Failure)
    assert "rag.ask" in result.message


async def test_ask_returns_answer_and_citations() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    answerer = _make_answer_provider("Employees get 15 vacation days.")
    svc = RAGService(session, embedder, answerer)

    doc_id = uuid4()
    chunk = _make_chunk(ctx.tenant_id, uuid4(), doc_id)
    svc._chunks.search_similar = AsyncMock(  # type: ignore[method-assign]
        return_value=[(chunk, "policy.txt")]
    )

    req = AskRequest(project_id=uuid4(), question="How many vacation days?")
    result = await svc.ask(req, ctx)
    assert isinstance(result, Success)
    assert "15 vacation days" in result.value.answer
    assert len(result.value.citations) == 1
    assert result.value.citations[0].filename == "policy.txt"


async def test_ask_citations_contain_document_id() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    answerer = _make_answer_provider("Answer.")
    svc = RAGService(session, embedder, answerer)

    doc_id = uuid4()
    chunk = _make_chunk(ctx.tenant_id, uuid4(), doc_id)
    svc._chunks.search_similar = AsyncMock(  # type: ignore[method-assign]
        return_value=[(chunk, "report.txt")]
    )

    req = AskRequest(project_id=uuid4(), question="Question?")
    result = await svc.ask(req, ctx)
    assert isinstance(result, Success)
    assert result.value.citations[0].document_id == doc_id


async def test_ask_no_chunks_returns_safe_response() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    svc = RAGService(session, embedder, _make_answer_provider())
    svc._chunks.search_similar = AsyncMock(return_value=[])  # type: ignore[method-assign]

    req = AskRequest(project_id=uuid4(), question="Anything?")
    result = await svc.ask(req, ctx)
    assert isinstance(result, Success)
    assert "No relevant documents" in result.value.answer
    assert result.value.citations == []


async def test_ask_ollama_unavailable_returns_failure() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    answerer = _make_answer_provider()
    answerer.generate = AsyncMock(
        side_effect=AIProviderUnavailableError("Ollama not reachable")
    )
    svc = RAGService(session, embedder, answerer)

    doc_id = uuid4()
    chunk = _make_chunk(ctx.tenant_id, uuid4(), doc_id)
    svc._chunks.search_similar = AsyncMock(  # type: ignore[method-assign]
        return_value=[(chunk, "doc.txt")]
    )

    req = AskRequest(project_id=uuid4(), question="?")
    result = await svc.ask(req, ctx)
    assert isinstance(result, Failure)
    assert isinstance(result.error, AIProviderUnavailableError)


async def test_ask_usage_record_created() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    answerer = _make_answer_provider("Answer.")
    svc = RAGService(session, embedder, answerer)

    doc_id = uuid4()
    chunk = _make_chunk(ctx.tenant_id, uuid4(), doc_id)
    svc._chunks.search_similar = AsyncMock(  # type: ignore[method-assign]
        return_value=[(chunk, "doc.txt")]
    )

    req = AskRequest(project_id=uuid4(), question="?")
    result = await svc.ask(req, ctx)
    assert isinstance(result, Success)
    # Usage repository calls session.flush() — verify session interaction
    assert session.flush.called or session.execute.called


async def test_ask_usage_failure_is_non_fatal() -> None:
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    answerer = _make_answer_provider("Answer.")
    svc = RAGService(session, embedder, answerer)

    doc_id = uuid4()
    chunk = _make_chunk(ctx.tenant_id, uuid4(), doc_id)
    svc._chunks.search_similar = AsyncMock(  # type: ignore[method-assign]
        return_value=[(chunk, "doc.txt")]
    )
    svc._usage.increment = AsyncMock(side_effect=RuntimeError("DB down"))  # type: ignore[method-assign]

    req = AskRequest(project_id=uuid4(), question="?")
    result = await svc.ask(req, ctx)
    # Usage failure must not prevent the answer from being returned.
    assert isinstance(result, Success)
    assert result.value.answer == "Answer."


async def test_ask_does_not_log_question(caplog: pytest.LogCaptureFixture) -> None:
    sensitive = "PRIVATE_QUESTION_CONTENT_DO_NOT_LOG_XYZ"
    ctx = _ctx()
    session = _make_session()
    embedder = _make_embedding_provider()
    answerer = _make_answer_provider()
    svc = RAGService(session, embedder, answerer)
    svc._chunks.search_similar = AsyncMock(return_value=[])  # type: ignore[method-assign]

    req = AskRequest(project_id=uuid4(), question=sensitive)
    with caplog.at_level(logging.DEBUG, logger="app.rag"):
        await svc.ask(req, ctx)
    for record in caplog.records:
        assert sensitive not in record.getMessage()


# ── list_documents ────────────────────────────────────────────────────────────


async def test_list_documents_missing_permission_returns_failure() -> None:
    ctx = _ctx(frozenset())
    session = _make_session()
    svc = RAGService(session, _make_embedding_provider())
    result = await svc.list_documents(uuid4(), ctx)
    assert isinstance(result, Failure)
    assert "rag.search" in result.message


async def test_list_documents_returns_empty_list() -> None:
    ctx = _ctx()
    session = _make_session()
    svc = RAGService(session, _make_embedding_provider())
    svc._docs.list_by_project = AsyncMock(return_value=[])  # type: ignore[method-assign]
    result = await svc.list_documents(uuid4(), ctx)
    assert isinstance(result, Success)
    assert result.value == []
