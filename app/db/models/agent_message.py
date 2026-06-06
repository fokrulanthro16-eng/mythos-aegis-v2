from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, UUIDPrimaryKeyMixin


class AgentMessage(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """One message in an agent session — user, assistant, or tool result.

    Messages are immutable; only created_at is tracked.
    tool_input / tool_output are JSON stored as Text (never contains secrets).
    """

    __tablename__ = "agent_messages"
    __table_args__ = (
        Index("ix_agent_message_session_id", "session_id"),
        Index("ix_agent_message_tenant_created", "tenant_id", "created_at"),
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # user | assistant | tool
    content: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None
    )
    # JSON stored as text to avoid pgvector/JSONB extension requirements.
    tool_input: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    tool_output: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
