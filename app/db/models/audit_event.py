from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ActorType(StrEnum):
    USER = "user"
    API_KEY = "api_key"
    SYSTEM = "system"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class AuditEvent(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Immutable audit log.  Never store raw JWTs, secrets, or passwords here."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_event_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_audit_event_tenant_id_action", "tenant_id", "action"),
    )

    actor_id: Mapped[UUID | None] = mapped_column(default=None)
    actor_type: Mapped[str] = mapped_column(String(20), default=ActorType.SYSTEM)
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str | None] = mapped_column(String(80), default=None)
    resource_id: Mapped[UUID | None] = mapped_column(default=None)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(512), default=None)
    outcome: Mapped[str] = mapped_column(String(20), default=AuditOutcome.SUCCESS)
    # Sanitized metadata — MUST NOT contain secrets, tokens, or passwords.
    extra_json: Mapped[str | None] = mapped_column(Text, default=None)
