"""Vision event audit model — tracks image/PDF analysis operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, UUIDPrimaryKeyMixin


class VisionEvent(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "vision_events"
    __table_args__ = (
        Index("ix_vision_event_tenant_created", "tenant_id", "created_at"),
        Index("ix_vision_event_tenant_project", "tenant_id", "project_id"),
    )

    user_id: Mapped[UUID] = mapped_column(index=True)
    filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    model_used: Mapped[str] = mapped_column(String(200))
    prompt_chars: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_chars: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    project_id: Mapped[UUID | None] = mapped_column(nullable=True, default=None)
    indexed_into_rag: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
