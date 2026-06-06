"""WorkflowExecution — a single run of a WorkflowDefinition."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import TenantMixin, UUIDPrimaryKeyMixin


class WorkflowExecution(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "workflow_executions"
    __table_args__ = (
        Index("ix_workflow_exec_tenant_status", "tenant_id", "status"),
        Index("ix_workflow_exec_workflow_id", "workflow_id"),
    )

    workflow_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # pending | running | completed | failed | cancelled
    input_json: Mapped[str] = mapped_column(Text, default="{}", server_default="'{}'")
    output_json: Mapped[str] = mapped_column(Text, default="{}", server_default="'{}'")
    triggered_by: Mapped[UUID] = mapped_column(nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(nullable=True, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
