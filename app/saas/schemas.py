"""Pydantic schemas for the SaaS layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Tenant ────────────────────────────────────────────────────────────────────


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    plan: str = Field(default="free")
    display_name: str | None = None


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str
    status: str
    display_name: str | None
    created_at: datetime
    updated_at: datetime


# ── Tenant Member ─────────────────────────────────────────────────────────────


class MemberInvite(BaseModel):
    user_id: UUID
    role: str = Field(default="member")
    invited_by: UUID | None = None


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    role: str
    invited_by: UUID | None
    accepted_at: datetime | None
    created_at: datetime


# ── Project ───────────────────────────────────────────────────────────────────


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


# ── API Key ───────────────────────────────────────────────────────────────────


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    project_id: UUID | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiKeyRead(BaseModel):
    """Returned for list/get operations — raw key is never included."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    project_id: UUID | None
    name: str
    key_prefix: str
    scopes: str | None
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    is_active: bool
    created_at: datetime


class ApiKeyCreated(ApiKeyRead):
    """Returned only at creation.  ``raw_key`` is shown exactly once."""

    raw_key: str


# ── Subscription ──────────────────────────────────────────────────────────────


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    plan: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    trial_ends_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime


# ── Usage Record ──────────────────────────────────────────────────────────────


class UsageRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    project_id: UUID | None
    billing_period: str
    request_count: int
    ai_call_count: int
    sql_airlock_blocks: int
    rate_limit_blocks: int
    token_usage: int
    updated_at: datetime


# ── Audit Event ───────────────────────────────────────────────────────────────


class AuditEventCreate(BaseModel):
    actor_id: UUID | None = None
    actor_type: str = "system"
    action: str = Field(min_length=1, max_length=100)
    resource_type: str | None = None
    resource_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    outcome: str = "success"
    # Caller is responsible for not passing secrets here.
    extra: dict[str, str] | None = None


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    actor_id: UUID | None
    actor_type: str
    action: str
    resource_type: str | None
    resource_id: UUID | None
    ip_address: str | None
    outcome: str
    created_at: datetime


# ── Security Event ────────────────────────────────────────────────────────────


class SecurityEventCreate(BaseModel):
    event_type: str
    severity: str = "info"
    actor_id: UUID | None = None
    ip_address: str | None = None
    detail: str | None = None


class SecurityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    event_type: str
    severity: str
    actor_id: UUID | None
    ip_address: str | None
    detail: str | None
    resolved_at: datetime | None
    created_at: datetime


# ── SQL Airlock Event ─────────────────────────────────────────────────────────


class SqlAirlockEventCreate(BaseModel):
    project_id: UUID | None = None
    actor_id: UUID | None = None
    action: str
    blocked_at_stage: str | None = None
    block_reason: str | None = None
    # Pass the raw query here; the service hashes it and discards the original.
    raw_query: str | None = None
    duration_ms: int | None = None
    rows_returned: int | None = None


class SqlAirlockEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    project_id: UUID | None
    actor_id: UUID | None
    action: str
    blocked_at_stage: str | None
    block_reason: str | None
    query_fingerprint: str | None
    duration_ms: int | None
    rows_returned: int | None
    created_at: datetime


# ── Rate Limit Event ──────────────────────────────────────────────────────────


class RateLimitEventCreate(BaseModel):
    actor_id: UUID | None = None
    ip_address: str | None = None
    policy_name: str
    endpoint: str
    limit_value: int
    window_seconds: int
    current_count: int
    retry_after_seconds: int | None = None


class RateLimitEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    actor_id: UUID | None
    ip_address: str | None
    policy_name: str
    endpoint: str
    limit_value: int
    window_seconds: int
    current_count: int
    retry_after_seconds: int | None
    created_at: datetime


# ── System Health Snapshot ────────────────────────────────────────────────────


class SystemHealthSnapshotCreate(BaseModel):
    overall_status: str = "healthy"
    api_latency_ms: float | None = None
    db_latency_ms: float | None = None
    active_tenants: int | None = None
    requests_last_hour: int | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None
    error_rate_percent: float | None = None


class SystemHealthSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    overall_status: str
    api_latency_ms: float | None
    db_latency_ms: float | None
    active_tenants: int | None
    requests_last_hour: int | None
    cpu_percent: float | None
    memory_percent: float | None
    error_rate_percent: float | None
    created_at: datetime
