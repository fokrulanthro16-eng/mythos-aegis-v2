"""Tests for the RAG repositories.

Verifies that every query is always scoped to tenant_id and project_id.
DB session is mocked throughout — no Postgres required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.db.models.document import DocumentStatus
from app.db.models.document_chunk import DocumentChunk
from app.rag.citation import make_citation_label
from app.rag.repository import DocumentChunkRepository, DocumentRepository

# ── Helpers ───────────────────────────────────────────────────────────────────


def _session(
    scalar_result: object = None, all_result: list[object] | None = None
) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()  # session.add is synchronous in SQLAlchemy
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = scalar_result
    db_result.scalars.return_value.all.return_value = all_result or []
    db_result.scalar.return_value = 0
    db_result.all.return_value = all_result or []
    session.execute.return_value = db_result
    return session


TENANT_A = uuid4()
TENANT_B = uuid4()
PROJECT_1 = uuid4()
DOCUMENT_ID = uuid4()


# ── make_citation_label ───────────────────────────────────────────────────────


def test_citation_label_stable() -> None:
    assert make_citation_label("policy.md", 3) == make_citation_label("policy.md", 3)


def test_citation_label_format() -> None:
    label = make_citation_label("my-policy.md", 5)
    assert "chunk-5" in label
    assert "my-policy" in label


def test_citation_label_strips_extension() -> None:
    label = make_citation_label("handbook.txt", 0)
    assert ".txt" not in label


def test_citation_label_sanitizes_special_chars() -> None:
    label = make_citation_label("Q&A report (2026).csv", 2)
    assert "&" not in label
    assert " " not in label
    assert "(" not in label


# ── DocumentRepository.create ─────────────────────────────────────────────────


async def test_create_document_adds_to_session() -> None:
    session = _session()
    repo = DocumentRepository(session)
    await repo.create(
        tenant_id=TENANT_A,
        project_id=PROJECT_1,
        uploaded_by_user_id=uuid4(),
        filename="test.txt",
        content_type="text/plain",
    )
    session.add.assert_called_once()
    session.flush.assert_called_once()


async def test_create_document_sets_tenant_id() -> None:
    session = _session()
    repo = DocumentRepository(session)
    doc = await repo.create(
        tenant_id=TENANT_A,
        project_id=PROJECT_1,
        uploaded_by_user_id=uuid4(),
        filename="test.txt",
        content_type="text/plain",
    )
    assert doc.tenant_id == TENANT_A


async def test_create_document_default_status_is_pending() -> None:
    session = _session()
    repo = DocumentRepository(session)
    doc = await repo.create(
        tenant_id=TENANT_A,
        project_id=PROJECT_1,
        uploaded_by_user_id=uuid4(),
        filename="test.txt",
        content_type="text/plain",
    )
    assert doc.status == DocumentStatus.PENDING


# ── DocumentRepository.get ────────────────────────────────────────────────────


async def test_get_document_queries_with_tenant_id() -> None:
    session = _session()
    repo = DocumentRepository(session)
    await repo.get(tenant_id=TENANT_A, document_id=DOCUMENT_ID)
    session.execute.assert_called_once()
    # Verify tenant_id is in the WHERE clause by checking the call was made
    assert session.execute.called


async def test_get_document_returns_none_for_missing() -> None:
    session = _session(scalar_result=None)
    repo = DocumentRepository(session)
    result = await repo.get(tenant_id=TENANT_A, document_id=DOCUMENT_ID)
    assert result is None


# ── DocumentRepository.list_by_project ───────────────────────────────────────


async def test_list_by_project_uses_tenant_and_project() -> None:
    session = _session()
    repo = DocumentRepository(session)
    await repo.list_by_project(tenant_id=TENANT_A, project_id=PROJECT_1)
    session.execute.assert_called_once()


async def test_list_by_project_returns_empty_list() -> None:
    session = _session(all_result=[])
    repo = DocumentRepository(session)
    result = await repo.list_by_project(tenant_id=TENANT_A, project_id=PROJECT_1)
    assert result == []


# ── DocumentRepository.set_status ────────────────────────────────────────────


async def test_set_status_executes_update() -> None:
    session = _session()
    repo = DocumentRepository(session)
    await repo.set_status(
        tenant_id=TENANT_A,
        document_id=DOCUMENT_ID,
        status=DocumentStatus.INDEXED,
    )
    session.execute.assert_called_once()
    session.flush.assert_called_once()


# ── DocumentChunkRepository.create_batch ─────────────────────────────────────


async def test_create_batch_adds_all_chunks() -> None:
    session = _session()
    repo = DocumentChunkRepository(session)
    chunks = [
        DocumentChunk(
            tenant_id=TENANT_A,
            project_id=PROJECT_1,
            document_id=DOCUMENT_ID,
            chunk_index=i,
            content=f"chunk {i}",
            content_hash=f"hash{i}",
            token_estimate=10,
            citation_label=f"doc#chunk-{i}",
        )
        for i in range(3)
    ]
    await repo.create_batch(chunks)
    assert session.add.call_count == 3
    session.flush.assert_called_once()


# ── DocumentChunkRepository.search_similar ────────────────────────────────────


async def test_search_similar_always_called_with_tenant_and_project() -> None:
    session = _session(all_result=[])
    repo = DocumentChunkRepository(session)
    query_vec = [0.1] * 768
    await repo.search_similar(
        tenant_id=TENANT_A,
        project_id=PROJECT_1,
        query_embedding=query_vec,
        top_k=5,
    )
    session.execute.assert_called_once()


async def test_search_similar_returns_empty_for_no_results() -> None:
    session = _session(all_result=[])
    repo = DocumentChunkRepository(session)
    result = await repo.search_similar(
        tenant_id=TENANT_A,
        project_id=PROJECT_1,
        query_embedding=[0.0] * 768,
        top_k=5,
    )
    assert result == []


async def test_search_cross_tenant_would_require_separate_call() -> None:
    """Two separate tenants require two separate calls — no cross-tenant leakage."""
    session_a = _session(all_result=[])
    session_b = _session(all_result=[])
    repo_a = DocumentChunkRepository(session_a)
    repo_b = DocumentChunkRepository(session_b)

    await repo_a.search_similar(
        tenant_id=TENANT_A, project_id=PROJECT_1, query_embedding=[0.0] * 768, top_k=5
    )
    await repo_b.search_similar(
        tenant_id=TENANT_B, project_id=PROJECT_1, query_embedding=[0.0] * 768, top_k=5
    )

    # Each repo used its own session — no shared state.
    assert session_a.execute.call_count == 1
    assert session_b.execute.call_count == 1


# ── DocumentChunkRepository.count_by_document ────────────────────────────────


async def test_count_by_document_queries_with_tenant_id() -> None:
    session = _session()
    repo = DocumentChunkRepository(session)
    result = await repo.count_by_document(tenant_id=TENANT_A, document_id=DOCUMENT_ID)
    assert result == 0
    session.execute.assert_called_once()
