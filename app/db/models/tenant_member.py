from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class MemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class TenantMember(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "tenant_members"
    __table_args__ = (
        Index("ix_tenant_member_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_tenant_member_tenant_id_user_id", "tenant_id", "user_id"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default=MemberRole.MEMBER)
    invited_by: Mapped[UUID | None] = mapped_column(default=None)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
