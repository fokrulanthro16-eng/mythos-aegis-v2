from __future__ import annotations

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


class AgentSession(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """One multi-turn agent conversation session, scoped to a tenant + project + user."""

    __tablename__ = "agent_sessions"
    __table_args__ = (
        Index("ix_agent_session_tenant_user", "tenant_id", "user_id"),
        Index("ix_agent_session_tenant_project", "tenant_id", "project_id"),
        Index("ix_agent_session_tenant_created", "tenant_id", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(index=True)
    user_id: Mapped[UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(500), default="New conversation")
