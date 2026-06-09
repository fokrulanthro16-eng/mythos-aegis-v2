"""workflow_engine — add workflow automation tables for Layer IX.

Revision ID: f3a8d1c5e2b7
Revises: a9f2c4b8e1d3
Create Date: 2026-06-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a8d1c5e2b7"
down_revision: str = "a9f2c4b8e1d3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ── workflow_definitions ──────────────────────────────────────────────────
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("steps_json", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_def_tenant_active",
        "workflow_definitions",
        ["tenant_id", "is_active"],
    )
    op.create_index(
        "ix_workflow_def_tenant_name",
        "workflow_definitions",
        ["tenant_id", "name"],
    )
    op.create_index(
        "ix_workflow_definitions_tenant_id",
        "workflow_definitions",
        ["tenant_id"],
    )

    # ── workflow_executions ───────────────────────────────────────────────────
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column(
            "input_json",
            sa.Text(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column(
            "output_json",
            sa.Text(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column("triggered_by", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_exec_tenant_status",
        "workflow_executions",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_workflow_exec_workflow_id",
        "workflow_executions",
        ["workflow_id"],
    )
    op.create_index(
        "ix_workflow_executions_tenant_id",
        "workflow_executions",
        ["tenant_id"],
    )

    # ── workflow_step_executions ──────────────────────────────────────────────
    op.create_table(
        "workflow_step_executions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.String(100), nullable=False),
        sa.Column("step_name", sa.String(200), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column(
            "input_json",
            sa.Text(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column(
            "output_json",
            sa.Text(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wf_step_exec_execution_id",
        "workflow_step_executions",
        ["execution_id"],
    )
    op.create_index(
        "ix_wf_step_exec_execution_status",
        "workflow_step_executions",
        ["execution_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wf_step_exec_execution_status",
        table_name="workflow_step_executions",
    )
    op.drop_index(
        "ix_wf_step_exec_execution_id",
        table_name="workflow_step_executions",
    )
    op.drop_table("workflow_step_executions")

    op.drop_index("ix_workflow_executions_tenant_id", table_name="workflow_executions")
    op.drop_index("ix_workflow_exec_workflow_id", table_name="workflow_executions")
    op.drop_index("ix_workflow_exec_tenant_status", table_name="workflow_executions")
    op.drop_table("workflow_executions")

    op.drop_index(
        "ix_workflow_definitions_tenant_id",
        table_name="workflow_definitions",
    )
    op.drop_index("ix_workflow_def_tenant_name", table_name="workflow_definitions")
    op.drop_index("ix_workflow_def_tenant_active", table_name="workflow_definitions")
    op.drop_table("workflow_definitions")
