"""SaaS repositories with strict tenant isolation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TenantIsolationError
from app.db.models.api_key import ApiKey
from app.db.models.audit_event import AuditEvent
from app.db.models.project import Project
from app.db.models.rate_limit_event import RateLimitEvent
from app.db.models.security_event import SecurityEvent
from app.db.models.sql_airlock_event import SqlAirlockEvent
from app.db.models.subscription import Subscription
from app.db.models.system_health_snapshot import SystemHealthSnapshot
from app.db.models.tenant import Tenant
from app.db.models.tenant_member import TenantMember
from app.db.models.usage_record import UsageRecord


def _require_tenant(tenant_id: UUID | None, context: str) -> UUID:
    if tenant_id is None:
        raise TenantIsolationError(f"{context} requires tenant_id")
    return tenant_id


# ── Tenant ────────────────────────────────────────────────────────────────────


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        slug: str,
        plan: str,
        status: str,
        display_name: str | None = None,
    ) -> Tenant:
        tenant = Tenant(
            name=name,
            slug=slug,
            plan=plan,
            status=status,
            display_name=display_name,
        )
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        result = await self._session.execute(
            select(Tenant).where(
                Tenant.id == tenant_id,
                Tenant.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self._session.execute(
            select(Tenant).where(
                Tenant.slug == slug,
                Tenant.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


# ── Tenant Member ─────────────────────────────────────────────────────────────


class TenantMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_member(
        self,
        *,
        tenant_id: UUID | None,
        user_id: UUID,
        role: str,
        invited_by: UUID | None = None,
    ) -> TenantMember:
        tid = _require_tenant(tenant_id, "TenantMemberRepository")
        member = TenantMember(
            tenant_id=tid,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
        )
        self._session.add(member)
        await self._session.flush()
        return member

    async def get_by_user(
        self, *, tenant_id: UUID | None, user_id: UUID
    ) -> TenantMember | None:
        tid = _require_tenant(tenant_id, "TenantMemberRepository")
        result = await self._session.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == tid,
                TenantMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_tenant(self, tenant_id: UUID | None) -> list[TenantMember]:
        tid = _require_tenant(tenant_id, "TenantMemberRepository")
        result = await self._session.execute(
            select(TenantMember).where(TenantMember.tenant_id == tid)
        )
        return list(result.scalars().all())


# ── Project ───────────────────────────────────────────────────────────────────


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: UUID | None,
        name: str,
        description: str | None = None,
    ) -> Project:
        tid = _require_tenant(tenant_id, "ProjectRepository")
        project = Project(tenant_id=tid, name=name, description=description)
        self._session.add(project)
        await self._session.flush()
        return project

    async def get_by_id(
        self, project_id: UUID, *, tenant_id: UUID | None
    ) -> Project | None:
        tid = _require_tenant(tenant_id, "ProjectRepository")
        result = await self._session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.tenant_id == tid,
                Project.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_tenant(self, tenant_id: UUID | None) -> list[Project]:
        tid = _require_tenant(tenant_id, "ProjectRepository")
        result = await self._session.execute(
            select(Project).where(
                Project.tenant_id == tid,
                Project.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())


# ── API Key ───────────────────────────────────────────────────────────────────


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: UUID | None,
        name: str,
        key_prefix: str,
        key_hash: str,
        project_id: UUID | None = None,
        scopes_json: str | None = None,
        expires_at: datetime | None = None,
    ) -> ApiKey:
        tid = _require_tenant(tenant_id, "ApiKeyRepository")
        key = ApiKey(
            tenant_id=tid,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            project_id=project_id,
            scopes=scopes_json,
            expires_at=expires_at,
        )
        self._session.add(key)
        await self._session.flush()
        return key

    async def get_by_id(self, key_id: UUID, *, tenant_id: UUID | None) -> ApiKey | None:
        tid = _require_tenant(tenant_id, "ApiKeyRepository")
        result = await self._session.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.tenant_id == tid,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        """Look up an API key by its SHA-256 hash for authentication."""
        result = await self._session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, key_id: UUID, *, tenant_id: UUID | None) -> bool:
        tid = _require_tenant(tenant_id, "ApiKeyRepository")
        result = await self._session.execute(
            update(ApiKey)
            .where(ApiKey.id == key_id, ApiKey.tenant_id == tid)
            .values(revoked_at=datetime.now(UTC))
            .returning(ApiKey.id)
        )
        return result.scalar_one_or_none() is not None

    async def list_for_tenant(self, tenant_id: UUID | None) -> list[ApiKey]:
        tid = _require_tenant(tenant_id, "ApiKeyRepository")
        result = await self._session.execute(
            select(ApiKey).where(ApiKey.tenant_id == tid)
        )
        return list(result.scalars().all())


# ── Subscription ──────────────────────────────────────────────────────────────


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: UUID | None,
        plan: str,
        status: str,
        current_period_start: datetime,
        current_period_end: datetime,
        trial_ends_at: datetime | None = None,
    ) -> Subscription:
        tid = _require_tenant(tenant_id, "SubscriptionRepository")
        sub = Subscription(
            tenant_id=tid,
            plan=plan,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            trial_ends_at=trial_ends_at,
        )
        self._session.add(sub)
        await self._session.flush()
        return sub

    async def get_for_tenant(self, tenant_id: UUID | None) -> Subscription | None:
        tid = _require_tenant(tenant_id, "SubscriptionRepository")
        result = await self._session.execute(
            select(Subscription).where(Subscription.tenant_id == tid)
        )
        return result.scalar_one_or_none()


# ── Usage Record ──────────────────────────────────────────────────────────────


class UsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(
        self,
        *,
        tenant_id: UUID | None,
        billing_period: str,
        project_id: UUID | None = None,
    ) -> UsageRecord:
        tid = _require_tenant(tenant_id, "UsageRepository")
        result = await self._session.execute(
            select(UsageRecord).where(
                UsageRecord.tenant_id == tid,
                UsageRecord.billing_period == billing_period,
                UsageRecord.project_id == project_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = UsageRecord(
                tenant_id=tid,
                billing_period=billing_period,
                project_id=project_id,
            )
            self._session.add(record)
            await self._session.flush()
        return record

    async def increment(
        self,
        *,
        tenant_id: UUID | None,
        billing_period: str,
        project_id: UUID | None = None,
        request_count: int = 0,
        ai_call_count: int = 0,
        sql_airlock_blocks: int = 0,
        rate_limit_blocks: int = 0,
        token_usage: int = 0,
    ) -> UsageRecord:
        record = await self.get_or_create(
            tenant_id=tenant_id,
            billing_period=billing_period,
            project_id=project_id,
        )
        record.request_count += request_count
        record.ai_call_count += ai_call_count
        record.sql_airlock_blocks += sql_airlock_blocks
        record.rate_limit_blocks += rate_limit_blocks
        record.token_usage += token_usage
        await self._session.flush()
        return record


# ── Event Repositories ────────────────────────────────────────────────────────


class EventRepository:
    """Append-only persistence for all event types."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist_audit_event(
        self,
        *,
        tenant_id: UUID | None,
        actor_id: UUID | None,
        actor_type: str,
        action: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        outcome: str,
        extra_json: str | None = None,
    ) -> AuditEvent:
        tid = _require_tenant(tenant_id, "EventRepository.audit")
        event = AuditEvent(
            tenant_id=tid,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            outcome=outcome,
            extra_json=extra_json,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def persist_security_event(
        self,
        *,
        tenant_id: UUID | None,
        event_type: str,
        severity: str,
        actor_id: UUID | None = None,
        ip_address: str | None = None,
        detail: str | None = None,
    ) -> SecurityEvent:
        tid = _require_tenant(tenant_id, "EventRepository.security")
        event = SecurityEvent(
            tenant_id=tid,
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            ip_address=ip_address,
            detail=detail,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def persist_sql_airlock_event(
        self,
        *,
        tenant_id: UUID | None,
        project_id: UUID | None,
        actor_id: UUID | None,
        action: str,
        blocked_at_stage: str | None,
        block_reason: str | None,
        query_fingerprint: str | None,
        duration_ms: int | None,
        rows_returned: int | None,
    ) -> SqlAirlockEvent:
        tid = _require_tenant(tenant_id, "EventRepository.sql_airlock")
        event = SqlAirlockEvent(
            tenant_id=tid,
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            blocked_at_stage=blocked_at_stage,
            block_reason=block_reason,
            query_fingerprint=query_fingerprint,
            duration_ms=duration_ms,
            rows_returned=rows_returned,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def persist_rate_limit_event(
        self,
        *,
        tenant_id: UUID | None,
        actor_id: UUID | None,
        ip_address: str | None,
        policy_name: str,
        endpoint: str,
        limit_value: int,
        window_seconds: int,
        current_count: int,
        retry_after_seconds: int | None,
    ) -> RateLimitEvent:
        tid = _require_tenant(tenant_id, "EventRepository.rate_limit")
        event = RateLimitEvent(
            tenant_id=tid,
            actor_id=actor_id,
            ip_address=ip_address,
            policy_name=policy_name,
            endpoint=endpoint,
            limit_value=limit_value,
            window_seconds=window_seconds,
            current_count=current_count,
            retry_after_seconds=retry_after_seconds,
        )
        self._session.add(event)
        await self._session.flush()
        return event


# ── System Health ─────────────────────────────────────────────────────────────


class SystemHealthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_snapshot(
        self,
        *,
        overall_status: str,
        api_latency_ms: float | None = None,
        db_latency_ms: float | None = None,
        active_tenants: int | None = None,
        requests_last_hour: int | None = None,
        cpu_percent: float | None = None,
        memory_percent: float | None = None,
        error_rate_percent: float | None = None,
    ) -> SystemHealthSnapshot:
        snapshot = SystemHealthSnapshot(
            overall_status=overall_status,
            api_latency_ms=api_latency_ms,
            db_latency_ms=db_latency_ms,
            active_tenants=active_tenants,
            requests_last_hour=requests_last_hour,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            error_rate_percent=error_rate_percent,
        )
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot


# ── Re-export json for callers that build extra_json ─────────────────────────

__all__ = [
    "ApiKeyRepository",
    "EventRepository",
    "ProjectRepository",
    "SubscriptionRepository",
    "SystemHealthRepository",
    "TenantMemberRepository",
    "TenantRepository",
    "UsageRepository",
    "json",
]
