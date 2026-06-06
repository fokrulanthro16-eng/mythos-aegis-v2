from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ApiKey(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_key_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_api_key_prefix", "key_prefix", unique=True),
        Index("ix_api_key_hash", "key_hash", unique=True),
    )

    name: Mapped[str] = mapped_column(String(255))
    # First 20 chars of the raw key — shown in UI for identification, never full.
    key_prefix: Mapped[str] = mapped_column(String(30), unique=True)
    # SHA-256 hex digest of the raw key.  The raw key is never persisted.
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    project_id: Mapped[UUID | None] = mapped_column(default=None)
    scopes: Mapped[str | None] = mapped_column(Text, default=None)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        from datetime import UTC
        from datetime import datetime as dt

        if self.expires_at is None:
            return False
        return dt.now(UTC) > self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.is_revoked and not self.is_expired
