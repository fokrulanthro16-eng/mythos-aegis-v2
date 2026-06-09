"""vision_intelligence — add vision_events table for Layer VIII.

Revision ID: a9f2c4b8e1d3
Revises: e8c2a5f3b9d1
Create Date: 2026-06-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9f2c4b8e1d3"
down_revision: str = "e8c2a5f3b9d1"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vision_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("model_used", sa.String(200), nullable=False),
        sa.Column(
            "prompt_chars",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "output_chars",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column(
            "indexed_into_rag",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vision_event_tenant_created",
        "vision_events",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_vision_event_tenant_project",
        "vision_events",
        ["tenant_id", "project_id"],
    )
    op.create_index(
        "ix_vision_events_tenant_id",
        "vision_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_vision_events_user_id",
        "vision_events",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_vision_events_user_id", table_name="vision_events")
    op.drop_index("ix_vision_events_tenant_id", table_name="vision_events")
    op.drop_index("ix_vision_event_tenant_project", table_name="vision_events")
    op.drop_index("ix_vision_event_tenant_created", table_name="vision_events")
    op.drop_table("vision_events")
