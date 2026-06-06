"""WorkflowStepExecution — audit record for a single step within a run."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.common import UUIDPrimaryKeyMixin


class WorkflowStepExecution(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workflow_step_executions"
    __table_args__ = (
        Index("ix_wf_step_exec_execution_id", "execution_id"),
        Index("ix_wf_step_exec_execution_status", "execution_id", "status"),
    )

    execution_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(100), nullable=False)
    step_name: Mapped[str] = mapped_column(String(200), nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # pending | running | completed | failed | skipped
    input_json: Mapped[str] = mapped_column(Text, default="{}", server_default="'{}'")
    output_json: Mapped[str] = mapped_column(Text, default="{}", server_default="'{}'")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
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
