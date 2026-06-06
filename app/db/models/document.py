from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import (
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class DocumentStatus(StrEnum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_document_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_document_tenant_project", "tenant_id", "project_id"),
    )

    project_id: Mapped[UUID] = mapped_column(index=True)
    uploaded_by_user_id: Mapped[UUID]
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(
        String(50), default="upload", server_default="upload"
    )
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.PENDING, server_default="pending"
    )
