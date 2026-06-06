"""RAG repositories with strict tenant and project isolation.

Every query unconditionally filters by ``tenant_id`` AND ``project_id`` where
applicable.  Querying by ``document_id`` alone is never permitted.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document, DocumentStatus
from app.db.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uploaded_by_user_id: UUID,
        filename: str,
        content_type: str,
    ) -> Document:
        doc = Document(
            id=uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            content_type=content_type,
            status=DocumentStatus.PENDING,
        )
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def get(self, *, tenant_id: UUID, document_id: UUID) -> Document | None:
        """Fetch a document; always requires tenant_id for isolation."""
        result = await self._session.execute(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> list[Document]:
        """List all non-deleted documents for a tenant+project pair."""
        result = await self._session.execute(
            select(Document)
            .where(
                Document.tenant_id == tenant_id,
                Document.project_id == project_id,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def set_status(
        self, *, tenant_id: UUID, document_id: UUID, status: str
    ) -> None:
        """Update document status; always scoped to tenant_id."""
        await self._session.execute(
            update(Document)
            .where(
                Document.tenant_id == tenant_id,
                Document.id == document_id,
            )
            .values(status=status)
        )
        await self._session.flush()


class DocumentChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_batch(self, chunks: list[DocumentChunk]) -> None:
        """Persist a batch of chunks in one flush."""
        for chunk in chunks:
            self._session.add(chunk)
        await self._session.flush()

    async def search_similar(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[tuple[DocumentChunk, str]]:
        """Return the top-k chunks closest to *query_embedding* (cosine similarity).

        Always filters by tenant_id AND project_id.
        Returns (DocumentChunk, filename) tuples — raw embeddings are never
        included in the return value.

        Similarity is computed in Python using numpy cosine similarity so that
        no pgvector extension is required.  For large corpora, a follow-up
        migration can switch to the pgvector <=> operator and an IVFFlat index.
        """
        import numpy as np

        stmt = (
            select(DocumentChunk, Document.filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.project_id == project_id,
                DocumentChunk.embedding.isnot(None),
                Document.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        rows: list[Any] = list(result.all())

        if not rows:
            return []

        q = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return [(row[0], row[1]) for row in rows[:top_k]]

        scored: list[tuple[float, DocumentChunk, str]] = []
        for chunk, filename in rows:
            emb = np.array(chunk.embedding, dtype=np.float32)
            emb_norm = np.linalg.norm(emb)
            if emb_norm == 0:
                similarity = 0.0
            else:
                similarity = float(np.dot(q, emb) / (q_norm * emb_norm))
            scored.append((similarity, chunk, filename))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [(chunk, filename) for _, chunk, filename in scored[:top_k]]

    async def count_by_document(self, *, tenant_id: UUID, document_id: UUID) -> int:
        """Count chunks for a document; scoped to tenant for isolation."""
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.document_id == document_id,
            )
        )
        return int(result.scalar() or 0)
