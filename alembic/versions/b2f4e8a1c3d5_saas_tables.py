"""SaaS tables: tenants, members, projects, api_keys, events, usage, subscriptions.

Revision ID: b2f4e8a1c3d5
Revises: aef8c3b72d1a
Create Date: 2026-06-06 00:00:00.000000

Tables created
--------------
tenants               — root tenant entity (slug unique, plan, status)
tenant_members        — user membership in a tenant with role
projects              — tenant-scoped projects
api_keys              — hashed API keys (raw key never stored)
audit_events          — immutable audit log
security_events       — security-relevant events (JWT failures, RBAC denials …)
sql_airlock_events    — SQL Airlock decisions (query fingerprint, not raw SQL)
rate_limit_events     — rate-limiter policy enforcement records
usage_records         — aggregated usage counters per billing period
subscriptions         — tenant billing plan and period
system_health_snapshots — system-wide health snapshots (not tenant-scoped)

Every tenant-owned table carries:
  - UUID primary key
  - tenant_id     (multi-tenancy; no FK to tenants for scale-out flexibility)
  - created_at / updated_at  (UTC, server-side default)

Indexes
-------
- tenant_id + created_at  on every tenant-owned table
- tenant_id + event_type  on security_events
- tenant_id + project_id  on sql_airlock_events, usage_records
- api_key key_prefix      (unique)
- api_key key_hash        (unique)
- tenant slug             (unique)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2f4e8a1c3d5"
down_revision: str | None = "aef8c3b72d1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── tenants ───────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenant_created_at", "tenants", ["created_at"])
    op.create_index("ix_tenant_status", "tenants", ["status"])

    # ── tenant_members ────────────────────────────────────────────────────────
    op.create_table(
        "tenant_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_tenant_members_user_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenant_members"),
    )
    op.create_index("ix_tenant_members_tenant_id", "tenant_members", ["tenant_id"])
    op.create_index("ix_tenant_members_user_id", "tenant_members", ["user_id"])
    op.create_index(
        "ix_tenant_member_tenant_id_created_at",
        "tenant_members",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_tenant_member_tenant_id_user_id",
        "tenant_members",
        ["tenant_id", "user_id"],
    )

    # ── projects ──────────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index(
        "ix_project_tenant_id_created_at", "projects", ["tenant_id", "created_at"]
    )
    op.create_index("ix_project_tenant_id_id", "projects", ["tenant_id", "id"])

    # ── api_keys ──────────────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(30), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_api_keys"),
        sa.UniqueConstraint("key_prefix", name="uq_api_key_prefix"),
        sa.UniqueConstraint("key_hash", name="uq_api_key_hash"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index(
        "ix_api_key_tenant_id_created_at", "api_keys", ["tenant_id", "created_at"]
    )
    op.create_index("ix_api_key_prefix", "api_keys", ["key_prefix"], unique=True)
    op.create_index("ix_api_key_hash", "api_keys", ["key_hash"], unique=True)

    # ── audit_events ──────────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="system"),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="success"),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index(
        "ix_audit_event_tenant_id_created_at",
        "audit_events",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_audit_event_tenant_id_action",
        "audit_events",
        ["tenant_id", "action"],
    )

    # ── security_events ───────────────────────────────────────────────────────
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_security_events"),
    )
    op.create_index("ix_security_events_tenant_id", "security_events", ["tenant_id"])
    op.create_index(
        "ix_security_event_tenant_id_created_at",
        "security_events",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_security_event_tenant_id_event_type",
        "security_events",
        ["tenant_id", "event_type"],
    )
    op.create_index("ix_security_event_severity", "security_events", ["severity"])

    # ── sql_airlock_events ────────────────────────────────────────────────────
    op.create_table(
        "sql_airlock_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("blocked_at_stage", sa.String(80), nullable=True),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("query_fingerprint", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("rows_returned", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sql_airlock_events"),
    )
    op.create_index(
        "ix_sql_airlock_events_tenant_id", "sql_airlock_events", ["tenant_id"]
    )
    op.create_index(
        "ix_sql_airlock_tenant_id_created_at",
        "sql_airlock_events",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_sql_airlock_tenant_id_action",
        "sql_airlock_events",
        ["tenant_id", "action"],
    )
    op.create_index(
        "ix_sql_airlock_tenant_id_project_id",
        "sql_airlock_events",
        ["tenant_id", "project_id"],
    )

    # ── rate_limit_events ─────────────────────────────────────────────────────
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("policy_name", sa.String(100), nullable=False),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("current_count", sa.Integer(), nullable=False),
        sa.Column("retry_after_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rate_limit_events"),
    )
    op.create_index(
        "ix_rate_limit_events_tenant_id", "rate_limit_events", ["tenant_id"]
    )
    op.create_index(
        "ix_rate_limit_tenant_id_created_at",
        "rate_limit_events",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_rate_limit_tenant_id_policy_name",
        "rate_limit_events",
        ["tenant_id", "policy_name"],
    )

    # ── usage_records ─────────────────────────────────────────────────────────
    op.create_table(
        "usage_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("billing_period", sa.String(7), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column(
            "request_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "ai_call_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "sql_airlock_blocks",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "rate_limit_blocks",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "token_usage",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_records"),
        sa.UniqueConstraint(
            "tenant_id",
            "billing_period",
            "project_id",
            name="uq_usage_tenant_period_project",
        ),
    )
    op.create_index("ix_usage_records_tenant_id", "usage_records", ["tenant_id"])
    op.create_index(
        "ix_usage_tenant_id_created_at",
        "usage_records",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_usage_tenant_id_project_id",
        "usage_records",
        ["tenant_id", "project_id"],
    )

    # ── subscriptions ─────────────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(20), nullable=False, server_default="trialing"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_subscriptions"),
    )
    op.create_index(
        "ix_subscription_tenant_id", "subscriptions", ["tenant_id"], unique=True
    )
    op.create_index("ix_subscription_status", "subscriptions", ["status"])

    # ── system_health_snapshots ───────────────────────────────────────────────
    op.create_table(
        "system_health_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "overall_status",
            sa.String(20),
            nullable=False,
            server_default="healthy",
        ),
        sa.Column("api_latency_ms", sa.Float(), nullable=True),
        sa.Column("db_latency_ms", sa.Float(), nullable=True),
        sa.Column("active_tenants", sa.Integer(), nullable=True),
        sa.Column("requests_last_hour", sa.Integer(), nullable=True),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("memory_percent", sa.Float(), nullable=True),
        sa.Column("error_rate_percent", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_system_health_snapshots"),
    )
    op.create_index(
        "ix_health_snapshot_created_at",
        "system_health_snapshots",
        ["created_at"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order.
    op.drop_index("ix_health_snapshot_created_at", table_name="system_health_snapshots")
    op.drop_table("system_health_snapshots")

    op.drop_index("ix_subscription_status", table_name="subscriptions")
    op.drop_index("ix_subscription_tenant_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_usage_tenant_id_project_id", table_name="usage_records")
    op.drop_index("ix_usage_tenant_id_created_at", table_name="usage_records")
    op.drop_index("ix_usage_records_tenant_id", table_name="usage_records")
    op.drop_table("usage_records")

    op.drop_index("ix_rate_limit_tenant_id_policy_name", table_name="rate_limit_events")
    op.drop_index("ix_rate_limit_tenant_id_created_at", table_name="rate_limit_events")
    op.drop_index("ix_rate_limit_events_tenant_id", table_name="rate_limit_events")
    op.drop_table("rate_limit_events")

    op.drop_index(
        "ix_sql_airlock_tenant_id_project_id", table_name="sql_airlock_events"
    )
    op.drop_index("ix_sql_airlock_tenant_id_action", table_name="sql_airlock_events")
    op.drop_index(
        "ix_sql_airlock_tenant_id_created_at", table_name="sql_airlock_events"
    )
    op.drop_index("ix_sql_airlock_events_tenant_id", table_name="sql_airlock_events")
    op.drop_table("sql_airlock_events")

    op.drop_index("ix_security_event_severity", table_name="security_events")
    op.drop_index(
        "ix_security_event_tenant_id_event_type", table_name="security_events"
    )
    op.drop_index(
        "ix_security_event_tenant_id_created_at", table_name="security_events"
    )
    op.drop_index("ix_security_events_tenant_id", table_name="security_events")
    op.drop_table("security_events")

    op.drop_index("ix_audit_event_tenant_id_action", table_name="audit_events")
    op.drop_index("ix_audit_event_tenant_id_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_api_key_hash", table_name="api_keys")
    op.drop_index("ix_api_key_prefix", table_name="api_keys")
    op.drop_index("ix_api_key_tenant_id_created_at", table_name="api_keys")
    op.drop_index("ix_api_keys_tenant_id", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index("ix_project_tenant_id_id", table_name="projects")
    op.drop_index("ix_project_tenant_id_created_at", table_name="projects")
    op.drop_index("ix_projects_tenant_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_tenant_member_tenant_id_user_id", table_name="tenant_members")
    op.drop_index("ix_tenant_member_tenant_id_created_at", table_name="tenant_members")
    op.drop_index("ix_tenant_members_user_id", table_name="tenant_members")
    op.drop_index("ix_tenant_members_tenant_id", table_name="tenant_members")
    op.drop_table("tenant_members")

    op.drop_index("ix_tenant_status", table_name="tenants")
    op.drop_index("ix_tenant_created_at", table_name="tenants")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
