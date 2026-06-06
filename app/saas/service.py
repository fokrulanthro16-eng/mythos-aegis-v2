"""SaaS service layer: tenant onboarding, API key lifecycle, usage metering."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessRuleViolation
from app.db.models.audit_event import AuditEvent
from app.db.models.rate_limit_event import RateLimitEvent
from app.db.models.security_event import SecurityEvent
from app.db.models.sql_airlock_event import SqlAirlockEvent
from app.db.models.subscription import SubscriptionStatus
from app.db.models.tenant import TenantStatus
from app.saas.repository import (
    ApiKeyRepository,
    EventRepository,
    ProjectRepository,
    SubscriptionRepository,
    TenantMemberRepository,
    TenantRepository,
    UsageRepository,
)
from app.saas.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyRead,
    AuditEventCreate,
    AuditEventRead,
    MemberInvite,
    MemberRead,
    ProjectCreate,
    ProjectRead,
    RateLimitEventCreate,
    RateLimitEventRead,
    SecurityEventCreate,
    SecurityEventRead,
    SqlAirlockEventCreate,
    SqlAirlockEventRead,
    SubscriptionRead,
    TenantCreate,
    TenantRead,
    UsageRecordRead,
)

# Patterns that must never appear in persisted event detail/extra fields.
_JWT_RE = re.compile(r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")
_SECRET_KEY_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]\s*\S+"
)
_SENSITIVE_DICT_KEYS = frozenset(
    {"password", "passwd", "pwd", "secret", "token", "api_key", "jwt", "key"}
)

# Trial period length in days.
_TRIAL_DAYS = 14


# ── Low-level helpers (module-level so tests can import them directly) ─────────


def generate_api_key() -> tuple[str, str, str]:
    """Return ``(raw_key, key_prefix, key_hash)``.

    * ``raw_key`` – shown to the user once; never stored.
    * ``key_prefix`` – first 20 chars; stored for UI display.
    * ``key_hash`` – SHA-256 hex of raw_key; stored for verification.
    """
    random_part = secrets.token_urlsafe(32)
    raw_key = f"aegis_live_{random_part}"
    key_prefix = raw_key[:20]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_prefix, key_hash


def hash_api_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of *raw_key*."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def sanitize_detail(text: str | None) -> str | None:
    """Strip JWT-like strings and credential patterns from free-text fields."""
    if text is None:
        return None
    text = _JWT_RE.sub("[REDACTED_TOKEN]", text)
    text = _SECRET_KEY_RE.sub(r"\1=[REDACTED]", text)
    return text[:1000]


def sanitize_extra(extra: dict[str, str] | None) -> str | None:
    """JSON-serialise *extra*, dropping any keys that look like secrets."""
    if extra is None:
        return None
    cleaned = {k: v for k, v in extra.items() if k.lower() not in _SENSITIVE_DICT_KEYS}
    return json.dumps(cleaned) if cleaned else None


def fingerprint_query(raw_query: str | None) -> str | None:
    """Return the SHA-256 hex digest of the raw query string."""
    if raw_query is None:
        return None
    return hashlib.sha256(raw_query.encode()).hexdigest()


# ── SaasService ───────────────────────────────────────────────────────────────


class SaasService:
    """Orchestrates SaaS lifecycle operations using injected repositories."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tenants = TenantRepository(session)
        self._members = TenantMemberRepository(session)
        self._projects = ProjectRepository(session)
        self._keys = ApiKeyRepository(session)
        self._subscriptions = SubscriptionRepository(session)
        self._usage = UsageRepository(session)
        self._events = EventRepository(session)

    # ── Tenant onboarding ─────────────────────────────────────────────────────

    async def create_tenant(
        self, data: TenantCreate
    ) -> tuple[TenantRead, SubscriptionRead]:
        """Create a tenant with a default trial subscription."""
        existing = await self._tenants.get_by_slug(data.slug)
        if existing is not None:
            raise BusinessRuleViolation(f"Slug '{data.slug}' is already taken")

        tenant = await self._tenants.create(
            name=data.name,
            slug=data.slug,
            plan=data.plan,
            status=TenantStatus.TRIAL,
            display_name=data.display_name,
        )

        now = datetime.now(UTC)
        trial_end = now + timedelta(days=_TRIAL_DAYS)
        subscription = await self._subscriptions.create(
            tenant_id=tenant.id,
            plan=data.plan,
            status=SubscriptionStatus.TRIALING,
            current_period_start=now,
            current_period_end=trial_end,
            trial_ends_at=trial_end,
        )

        return TenantRead.model_validate(tenant), SubscriptionRead.model_validate(
            subscription
        )

    async def invite_member(self, tenant_id: UUID, data: MemberInvite) -> MemberRead:
        member = await self._members.add_member(
            tenant_id=tenant_id,
            user_id=data.user_id,
            role=data.role,
            invited_by=data.invited_by,
        )
        return MemberRead.model_validate(member)

    # ── Project management ────────────────────────────────────────────────────

    async def create_project(self, tenant_id: UUID, data: ProjectCreate) -> ProjectRead:
        project = await self._projects.create(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
        )
        return ProjectRead.model_validate(project)

    # ── API key lifecycle ─────────────────────────────────────────────────────

    async def create_api_key(
        self, tenant_id: UUID, data: ApiKeyCreate
    ) -> ApiKeyCreated:
        """Create an API key.  The ``raw_key`` in the response is shown once only."""
        raw_key, key_prefix, key_hash = generate_api_key()
        scopes_json = json.dumps(data.scopes) if data.scopes else None

        key = await self._keys.create(
            tenant_id=tenant_id,
            name=data.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            project_id=data.project_id,
            scopes_json=scopes_json,
            expires_at=data.expires_at,
        )

        read = ApiKeyRead.model_validate(key)
        return ApiKeyCreated(**read.model_dump(), raw_key=raw_key)

    async def revoke_api_key(self, tenant_id: UUID, key_id: UUID) -> bool:
        return await self._keys.revoke(key_id, tenant_id=tenant_id)

    async def verify_api_key(self, raw_key: str) -> ApiKeyRead | None:
        """Verify a raw key and return its metadata if valid (not revoked/expired)."""
        key_hash = hash_api_key(raw_key)
        key = await self._keys.get_by_hash(key_hash)
        if key is None or not key.is_active:
            return None
        return ApiKeyRead.model_validate(key)

    # ── Usage metering ────────────────────────────────────────────────────────

    async def record_usage(
        self,
        tenant_id: UUID,
        *,
        billing_period: str,
        project_id: UUID | None = None,
        request_count: int = 0,
        ai_call_count: int = 0,
        sql_airlock_blocks: int = 0,
        rate_limit_blocks: int = 0,
        token_usage: int = 0,
    ) -> UsageRecordRead:
        record = await self._usage.increment(
            tenant_id=tenant_id,
            billing_period=billing_period,
            project_id=project_id,
            request_count=request_count,
            ai_call_count=ai_call_count,
            sql_airlock_blocks=sql_airlock_blocks,
            rate_limit_blocks=rate_limit_blocks,
            token_usage=token_usage,
        )
        return UsageRecordRead.model_validate(record)

    # ── Event persistence ─────────────────────────────────────────────────────

    async def persist_audit_event(
        self, tenant_id: UUID, data: AuditEventCreate
    ) -> AuditEventRead:
        extra_json = sanitize_extra(data.extra)
        event: AuditEvent = await self._events.persist_audit_event(
            tenant_id=tenant_id,
            actor_id=data.actor_id,
            actor_type=data.actor_type,
            action=data.action,
            resource_type=data.resource_type,
            resource_id=data.resource_id,
            ip_address=data.ip_address,
            user_agent=data.user_agent,
            outcome=data.outcome,
            extra_json=extra_json,
        )
        return AuditEventRead.model_validate(event)

    async def persist_security_event(
        self, tenant_id: UUID, data: SecurityEventCreate
    ) -> SecurityEventRead:
        safe_detail = sanitize_detail(data.detail)
        event: SecurityEvent = await self._events.persist_security_event(
            tenant_id=tenant_id,
            event_type=data.event_type,
            severity=data.severity,
            actor_id=data.actor_id,
            ip_address=data.ip_address,
            detail=safe_detail,
        )
        return SecurityEventRead.model_validate(event)

    async def persist_sql_airlock_event(
        self, tenant_id: UUID, data: SqlAirlockEventCreate
    ) -> SqlAirlockEventRead:
        # Hash the raw query — never store the query text itself.
        qfp = fingerprint_query(data.raw_query)
        safe_reason = sanitize_detail(data.block_reason)
        event: SqlAirlockEvent = await self._events.persist_sql_airlock_event(
            tenant_id=tenant_id,
            project_id=data.project_id,
            actor_id=data.actor_id,
            action=data.action,
            blocked_at_stage=data.blocked_at_stage,
            block_reason=safe_reason,
            query_fingerprint=qfp,
            duration_ms=data.duration_ms,
            rows_returned=data.rows_returned,
        )
        return SqlAirlockEventRead.model_validate(event)

    async def persist_rate_limit_event(
        self, tenant_id: UUID, data: RateLimitEventCreate
    ) -> RateLimitEventRead:
        event: RateLimitEvent = await self._events.persist_rate_limit_event(
            tenant_id=tenant_id,
            actor_id=data.actor_id,
            ip_address=data.ip_address,
            policy_name=data.policy_name,
            endpoint=data.endpoint,
            limit_value=data.limit_value,
            window_seconds=data.window_seconds,
            current_count=data.current_count,
            retry_after_seconds=data.retry_after_seconds,
        )
        return RateLimitEventRead.model_validate(event)
