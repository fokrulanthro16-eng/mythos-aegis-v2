from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SecurityEventType(StrEnum):
    JWT_FAILURE = "jwt_failure"
    RBAC_DENIAL = "rbac_denial"
    SQL_BLOCK = "sql_block"
    RATE_LIMIT = "rate_limit"
    ISOLATION_VIOLATION = "isolation_violation"
    SECRET_ROTATION = "secret_rotation"  # pragma: allowlist secret
    AUTH_SUCCESS = "auth_success"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class EventSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEvent(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Security-relevant event.  Never store raw JWTs, secrets, or passwords."""

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_event_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_security_event_tenant_id_event_type", "tenant_id", "event_type"),
        Index("ix_security_event_severity", "severity"),
    )

    event_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20), default=EventSeverity.INFO)
    actor_id: Mapped[UUID | None] = mapped_column(default=None)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)
    # Sanitized description — MUST NOT contain tokens or credentials.
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
