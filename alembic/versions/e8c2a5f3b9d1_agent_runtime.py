"""Agent runtime: agent_sessions and agent_messages tables.

Revision ID: e8c2a5f3b9d1
Revises: c4e7d2f1a8b6
Create Date: 2026-06-06 00:00:00.000000

Tables created
--------------
agent_sessions  — multi-turn conversation session per tenant/project/user
agent_messages  — individual messages (user | assistant | tool) in a session

Memory model
------------
Messages are append-only; tool_input and tool_output are JSON stored as TEXT
(no PostgreSQL-extension dependency).  The created_at column on agent_messages
is used for chronological ordering.

Indexes
-------
- tenant_id + user_id    on agent_sessions
- tenant_id + project_id on agent_sessions
- tenant_id + created_at on agent_sessions
- session_id             on agent_messages
- tenant_id + created_at on agent_messages
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8c2a5f3b9d1"
down_revision: str | None = "c4e7d2f1a8b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── agent_sessions ────────────────────────────────────────────────────────
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "title",
            sa.String(500),
            nullable=False,
            server_default="New conversation",
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_session_tenant_user", "agent_sessions", ["tenant_id", "user_id"]
    )
    op.create_index(
        "ix_agent_session_tenant_project", "agent_sessions", ["tenant_id", "project_id"]
    )
    op.create_index(
        "ix_agent_session_tenant_created", "agent_sessions", ["tenant_id", "created_at"]
    )
    op.create_index("ix_agent_session_project_id", "agent_sessions", ["project_id"])
    op.create_index("ix_agent_session_user_id", "agent_sessions", ["user_id"])

    # ── agent_messages ────────────────────────────────────────────────────────
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("tool_input", sa.Text(), nullable=True),
        sa.Column("tool_output", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["agent_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_message_session_id", "agent_messages", ["session_id"])
    op.create_index("ix_agent_message_tenant_id", "agent_messages", ["tenant_id"])
    op.create_index(
        "ix_agent_message_tenant_created", "agent_messages", ["tenant_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("agent_messages")
    op.drop_table("agent_sessions")
