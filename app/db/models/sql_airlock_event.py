from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AirlockAction(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REWRITTEN = "rewritten"


class SqlAirlockEvent(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """SQL Airlock decision record.

    Raw SQL queries are NEVER stored.  Use ``query_fingerprint`` (SHA-256 of
    the canonical query) for correlation without exposing query content.
    """

    __tablename__ = "sql_airlock_events"
    __table_args__ = (
        Index("ix_sql_airlock_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_sql_airlock_tenant_id_action", "tenant_id", "action"),
        Index("ix_sql_airlock_tenant_id_project_id", "tenant_id", "project_id"),
    )

    project_id: Mapped[UUID | None] = mapped_column(default=None)
    actor_id: Mapped[UUID | None] = mapped_column(default=None)
    action: Mapped[str] = mapped_column(String(20))
    blocked_at_stage: Mapped[str | None] = mapped_column(String(80), default=None)
    # Human-readable policy reason — no raw SQL fragments allowed.
    block_reason: Mapped[str | None] = mapped_column(Text, default=None)
    # SHA-256 of the normalised query — never the query itself.
    query_fingerprint: Mapped[str | None] = mapped_column(String(64), default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    rows_returned: Mapped[int | None] = mapped_column(Integer, default=None)
