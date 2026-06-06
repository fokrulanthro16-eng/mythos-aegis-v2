from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

# Use PostgreSQL ARRAY(Float) for portability — works without the pgvector
# extension.  Similarity search is done in Python (see repository.py).
# When pgvector is available in the environment, the migration can upgrade
# the column to vector(768) and enable index-accelerated ANN search.
_EMBEDDING_COL_TYPE: Any = ARRAY(Float)


class DocumentChunk(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """One text chunk of a Document with its float-array embedding."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_chunk_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_chunk_tenant_project", "tenant_id", "project_id"),
        Index("ix_chunk_document_id", "document_id"),
        Index("ix_chunk_content_hash", "content_hash"),
    )

    project_id: Mapped[UUID] = mapped_column(index=True)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # FLOAT4[] column; nullable until embedding is computed during indexing.
    embedding: Mapped[list[float] | None] = mapped_column(
        _EMBEDDING_COL_TYPE, nullable=True, default=None
    )
    citation_label: Mapped[str] = mapped_column(String(500))
