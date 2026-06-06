"""Tests for the SaaS layer: helpers, schemas, models, repositories, service."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Table

from app.core.exceptions import BusinessRuleViolation, TenantIsolationError
from app.db.models.api_key import ApiKey
from app.db.models.audit_event import AuditEvent
from app.db.models.rate_limit_event import RateLimitEvent
from app.db.models.security_event import EventSeverity, SecurityEvent
from app.db.models.sql_airlock_event import AirlockAction, SqlAirlockEvent
from app.db.models.subscription import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.db.models.system_health_snapshot import HealthStatus, SystemHealthSnapshot
from app.db.models.tenant import Tenant, TenantPlan, TenantStatus
from app.db.models.tenant_member import MemberRole
from app.db.models.usage_record import UsageRecord
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
    SecurityEventCreate,
    SqlAirlockEventCreate,
    TenantCreate,
)
from app.saas.service import (
    SaasService,
    fingerprint_query,
    generate_api_key,
    hash_api_key,
    sanitize_detail,
    sanitize_extra,
)


def _tbl(model_cls: type) -> Table:
    return cast(Table, model_cls.__table__)  # type: ignore[attr-defined]


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    return session


@pytest.fixture
def tenant_repo(mock_session: AsyncMock) -> TenantRepository:
    return TenantRepository(mock_session)


@pytest.fixture
def member_repo(mock_session: AsyncMock) -> TenantMemberRepository:
    return TenantMemberRepository(mock_session)


@pytest.fixture
def project_repo(mock_session: AsyncMock) -> ProjectRepository:
    return ProjectRepository(mock_session)


@pytest.fixture
def api_key_repo(mock_session: AsyncMock) -> ApiKeyRepository:
    return ApiKeyRepository(mock_session)


@pytest.fixture
def usage_repo(mock_session: AsyncMock) -> UsageRepository:
    return UsageRepository(mock_session)


@pytest.fixture
def event_repo(mock_session: AsyncMock) -> EventRepository:
    return EventRepository(mock_session)


@pytest.fixture
def subscription_repo(mock_session: AsyncMock) -> SubscriptionRepository:
    return SubscriptionRepository(mock_session)


# ── generate_api_key ──────────────────────────────────────────────────────────


def test_generate_api_key_returns_three_parts() -> None:
    raw_key, prefix, key_hash = generate_api_key()
    assert raw_key
    assert prefix
    assert key_hash


def test_generate_api_key_starts_with_prefix() -> None:
    raw_key, _, _ = generate_api_key()
    assert raw_key.startswith("aegis_live_")


def test_generate_api_key_prefix_is_first_20_chars() -> None:
    raw_key, prefix, _ = generate_api_key()
    assert prefix == raw_key[:20]


def test_generate_api_key_hash_is_sha256_of_raw() -> None:
    raw_key, _, key_hash = generate_api_key()
    expected = hashlib.sha256(raw_key.encode()).hexdigest()
    assert key_hash == expected


def test_generate_api_key_hash_is_64_hex_chars() -> None:
    _, _, key_hash = generate_api_key()
    assert len(key_hash) == 64
    assert all(c in "0123456789abcdef" for c in key_hash)


def test_generate_api_key_is_unique_each_call() -> None:
    keys = {generate_api_key()[0] for _ in range(20)}
    assert len(keys) == 20


# ── hash_api_key ──────────────────────────────────────────────────────────────


def test_hash_api_key_deterministic() -> None:
    key = "some-raw-key"
    assert hash_api_key(key) == hash_api_key(key)


def test_hash_api_key_matches_sha256() -> None:
    raw = "aegis_live_testkey"
    assert hash_api_key(raw) == hashlib.sha256(raw.encode()).hexdigest()


def test_hash_api_key_different_inputs_differ() -> None:
    assert hash_api_key("key-a") != hash_api_key("key-b")


# ── sanitize_detail ───────────────────────────────────────────────────────────


def test_sanitize_detail_returns_none_for_none() -> None:
    assert sanitize_detail(None) is None


def test_sanitize_detail_strips_jwt_token() -> None:
    # All three segments must be ≥20 chars to match _JWT_RE.
    jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    text_with_jwt = f"auth header: {jwt}"
    result = sanitize_detail(text_with_jwt)
    assert result is not None
    # The long unique segment from the JWT payload must not appear in output.
    assert (
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
        not in result
    )  # noqa: E501


def test_sanitize_detail_strips_password_assignment() -> None:
    result = sanitize_detail("password=supersecret123")
    assert result is not None
    assert "supersecret123" not in result
    assert "[REDACTED]" in result


def test_sanitize_detail_strips_secret_colon_pattern() -> None:
    result = sanitize_detail("secret: my-vault-key")
    assert result is not None
    assert "my-vault-key" not in result


def test_sanitize_detail_strips_token_pattern() -> None:
    result = sanitize_detail("token=abc.def.ghi.jkl extra text")
    assert result is not None
    assert "abc.def.ghi.jkl" not in result


def test_sanitize_detail_preserves_safe_text() -> None:
    safe = "user login succeeded from 192.168.1.1"
    assert sanitize_detail(safe) == safe


def test_sanitize_detail_truncates_to_1000_chars() -> None:
    long_text = "x" * 2000
    result = sanitize_detail(long_text)
    assert result is not None
    assert len(result) == 1000


# ── sanitize_extra ────────────────────────────────────────────────────────────


def test_sanitize_extra_returns_none_for_none() -> None:
    assert sanitize_extra(None) is None


def test_sanitize_extra_drops_password_key() -> None:
    data = {"password": "secret123", "action": "login"}
    result = sanitize_extra(data)
    assert result is not None
    parsed = json.loads(result)
    assert "password" not in parsed
    assert parsed["action"] == "login"


def test_sanitize_extra_drops_token_key() -> None:
    data = {"token": "jwt-value", "user_id": "42"}
    result = sanitize_extra(data)
    assert result is not None
    assert "jwt-value" not in result


def test_sanitize_extra_drops_secret_key() -> None:
    data = {"secret": "my-secret", "endpoint": "/api/v1"}
    result = sanitize_extra(data)
    parsed = json.loads(result)  # type: ignore[arg-type]
    assert "secret" not in parsed


def test_sanitize_extra_drops_api_key_key() -> None:
    data = {"api_key": "sk-live-xxx", "region": "us-east-1"}
    result = sanitize_extra(data)
    parsed = json.loads(result)  # type: ignore[arg-type]
    assert "api_key" not in parsed
    assert parsed["region"] == "us-east-1"


def test_sanitize_extra_preserves_safe_keys() -> None:
    data = {"action": "query", "duration_ms": "42"}
    result = sanitize_extra(data)
    assert result is not None
    parsed = json.loads(result)
    assert parsed == data


def test_sanitize_extra_returns_none_when_all_keys_sensitive() -> None:
    data = {"password": "x", "token": "y"}
    assert sanitize_extra(data) is None


# ── fingerprint_query ─────────────────────────────────────────────────────────


def test_fingerprint_query_returns_none_for_none() -> None:
    assert fingerprint_query(None) is None


def test_fingerprint_query_returns_sha256() -> None:
    sql = "SELECT * FROM users"
    expected = hashlib.sha256(sql.encode()).hexdigest()
    assert fingerprint_query(sql) == expected


def test_fingerprint_query_is_deterministic() -> None:
    sql = "SELECT id FROM orders WHERE tenant_id = $1"
    assert fingerprint_query(sql) == fingerprint_query(sql)


def test_fingerprint_query_raw_sql_not_in_result() -> None:
    sql = "DROP TABLE users"
    fp = fingerprint_query(sql)
    assert sql not in (fp or "")


# ── ApiKey model: raw key never stored ────────────────────────────────────────


def test_api_key_schema_read_has_no_raw_key_field() -> None:
    fields = ApiKeyRead.model_fields
    assert "raw_key" not in fields


def test_api_key_schema_created_has_raw_key_field() -> None:
    fields = ApiKeyCreated.model_fields
    assert "raw_key" in fields


def test_api_key_model_has_no_raw_key_column() -> None:
    col_names = {c.name for c in _tbl(ApiKey).columns}
    assert "raw_key" not in col_names


def test_api_key_model_has_key_prefix_and_key_hash() -> None:
    col_names = {c.name for c in _tbl(ApiKey).columns}
    assert "key_prefix" in col_names
    assert "key_hash" in col_names


def test_api_key_is_active_true_when_not_revoked_or_expired() -> None:
    key = ApiKey(
        tenant_id=uuid4(),
        name="test",
        key_prefix="aegis_live_testp",
        key_hash="a" * 64,
    )
    assert key.is_active is True


def test_api_key_is_revoked_when_revoked_at_set() -> None:
    key = ApiKey(
        tenant_id=uuid4(),
        name="test",
        key_prefix="aegis_live_testp",
        key_hash="b" * 64,
        revoked_at=datetime.now(UTC),
    )
    assert key.is_revoked is True
    assert key.is_active is False


def test_api_key_is_expired_when_expires_at_in_past() -> None:
    key = ApiKey(
        tenant_id=uuid4(),
        name="test",
        key_prefix="aegis_live_testp",
        key_hash="c" * 64,
        expires_at=datetime(2000, 1, 1, tzinfo=UTC),
    )
    assert key.is_expired is True
    assert key.is_active is False


def test_api_key_not_expired_when_no_expiry() -> None:
    key = ApiKey(
        tenant_id=uuid4(),
        name="test",
        key_prefix="aegis_live_testp",
        key_hash="d" * 64,
    )
    assert key.is_expired is False


# ── Model: table structure ────────────────────────────────────────────────────


def test_tenant_tablename() -> None:
    assert Tenant.__tablename__ == "tenants"


def test_tenant_columns_present() -> None:
    col_names = {c.name for c in _tbl(Tenant).columns}
    assert {
        "id",
        "name",
        "slug",
        "plan",
        "status",
        "created_at",
        "updated_at",
    } <= col_names


def test_tenant_slug_has_unique_index() -> None:
    index_names = {idx.name for idx in _tbl(Tenant).indexes}
    assert any("slug" in (n or "") for n in index_names)


def test_api_key_indexes_present() -> None:
    index_names = {idx.name for idx in _tbl(ApiKey).indexes}
    assert "ix_api_key_prefix" in index_names
    assert "ix_api_key_hash" in index_names


def test_audit_event_tablename() -> None:
    assert AuditEvent.__tablename__ == "audit_events"


def test_security_event_tablename() -> None:
    assert SecurityEvent.__tablename__ == "security_events"


def test_sql_airlock_event_tablename() -> None:
    assert SqlAirlockEvent.__tablename__ == "sql_airlock_events"


def test_rate_limit_event_tablename() -> None:
    assert RateLimitEvent.__tablename__ == "rate_limit_events"


def test_usage_record_tablename() -> None:
    assert UsageRecord.__tablename__ == "usage_records"


def test_subscription_tablename() -> None:
    assert Subscription.__tablename__ == "subscriptions"


def test_system_health_snapshot_tablename() -> None:
    assert SystemHealthSnapshot.__tablename__ == "system_health_snapshots"


def test_system_health_snapshot_has_no_tenant_id() -> None:
    col_names = {c.name for c in _tbl(SystemHealthSnapshot).columns}
    assert "tenant_id" not in col_names


def test_usage_record_unique_constraint_present() -> None:
    constraint_names = {c.name for c in _tbl(UsageRecord).constraints}
    assert "uq_usage_tenant_period_project" in constraint_names


# ── Enums ─────────────────────────────────────────────────────────────────────


def test_tenant_plan_values() -> None:
    values = {p.value for p in TenantPlan}
    assert {"free", "starter", "growth", "business", "enterprise"} == values


def test_tenant_status_values() -> None:
    values = {s.value for s in TenantStatus}
    assert {"trial", "active", "suspended", "cancelled"} == values


def test_member_role_values() -> None:
    values = {r.value for r in MemberRole}
    assert "owner" in values
    assert "member" in values


def test_subscription_plan_values() -> None:
    values = {p.value for p in SubscriptionPlan}
    assert "free" in values


def test_subscription_status_values() -> None:
    values = {s.value for s in SubscriptionStatus}
    assert "trialing" in values
    assert "active" in values


def test_airlock_action_values() -> None:
    values = {a.value for a in AirlockAction}
    assert "allowed" in values
    assert "blocked" in values


def test_event_severity_values() -> None:
    values = {s.value for s in EventSeverity}
    assert "critical" in values
    assert "info" in values


def test_health_status_values() -> None:
    values = {s.value for s in HealthStatus}
    assert "healthy" in values
    assert "degraded" in values


# ── Repository isolation ──────────────────────────────────────────────────────


async def test_member_repo_raises_without_tenant(
    member_repo: TenantMemberRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await member_repo.add_member(tenant_id=None, user_id=uuid4(), role="member")


async def test_project_repo_create_raises_without_tenant(
    project_repo: ProjectRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await project_repo.create(tenant_id=None, name="proj")


async def test_project_repo_get_by_id_raises_without_tenant(
    project_repo: ProjectRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await project_repo.get_by_id(uuid4(), tenant_id=None)


async def test_project_repo_list_raises_without_tenant(
    project_repo: ProjectRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await project_repo.list_for_tenant(None)


async def test_api_key_repo_create_raises_without_tenant(
    api_key_repo: ApiKeyRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await api_key_repo.create(
            tenant_id=None,
            name="key",
            key_prefix="aegis_live_x",
            key_hash="a" * 64,
        )


async def test_api_key_repo_revoke_raises_without_tenant(
    api_key_repo: ApiKeyRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await api_key_repo.revoke(uuid4(), tenant_id=None)


async def test_api_key_repo_list_raises_without_tenant(
    api_key_repo: ApiKeyRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await api_key_repo.list_for_tenant(None)


async def test_usage_repo_get_or_create_raises_without_tenant(
    usage_repo: UsageRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await usage_repo.get_or_create(tenant_id=None, billing_period="2026-06")


async def test_event_repo_audit_raises_without_tenant(
    event_repo: EventRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await event_repo.persist_audit_event(
            tenant_id=None,
            actor_id=None,
            actor_type="system",
            action="login",
            outcome="success",
        )


async def test_event_repo_security_raises_without_tenant(
    event_repo: EventRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await event_repo.persist_security_event(
            tenant_id=None,
            event_type="jwt_failure",
            severity="warning",
        )


async def test_event_repo_sql_airlock_raises_without_tenant(
    event_repo: EventRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await event_repo.persist_sql_airlock_event(
            tenant_id=None,
            project_id=None,
            actor_id=None,
            action="block",
            blocked_at_stage=None,
            block_reason=None,
            query_fingerprint=None,
            duration_ms=None,
            rows_returned=None,
        )


async def test_event_repo_rate_limit_raises_without_tenant(
    event_repo: EventRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await event_repo.persist_rate_limit_event(
            tenant_id=None,
            actor_id=None,
            ip_address=None,
            policy_name="global",
            endpoint="/api/query",
            limit_value=100,
            window_seconds=60,
            current_count=101,
            retry_after_seconds=None,
        )


async def test_subscription_repo_raises_without_tenant(
    subscription_repo: SubscriptionRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await subscription_repo.get_for_tenant(None)


# ── Repository: isolation enforced with valid tenant ─────────────────────────


async def test_project_repo_list_returns_empty_with_valid_tenant(
    project_repo: ProjectRepository,
) -> None:
    result = await project_repo.list_for_tenant(uuid4())
    assert result == []


async def test_api_key_repo_get_by_hash_executes(
    api_key_repo: ApiKeyRepository, mock_session: AsyncMock
) -> None:
    await api_key_repo.get_by_hash("a" * 64)
    assert mock_session.execute.called


# ── Service: create_tenant raises on duplicate slug ───────────────────────────


async def test_create_tenant_raises_on_duplicate_slug(mock_session: AsyncMock) -> None:
    existing = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = result

    service = SaasService(mock_session)
    with pytest.raises(BusinessRuleViolation, match="already taken"):
        await service.create_tenant(
            TenantCreate(name="Acme", slug="acme-corp", plan="free")
        )


async def test_create_tenant_succeeds_with_new_slug(mock_session: AsyncMock) -> None:
    tenant_obj = MagicMock(spec=Tenant)
    tenant_obj.id = uuid4()
    tenant_obj.name = "Acme"
    tenant_obj.slug = "acme-new"
    tenant_obj.plan = "free"
    tenant_obj.status = "trial"
    tenant_obj.display_name = None
    tenant_obj.created_at = datetime.now(UTC)
    tenant_obj.updated_at = datetime.now(UTC)

    sub_obj = MagicMock(spec=Subscription)
    sub_obj.id = uuid4()
    sub_obj.tenant_id = tenant_obj.id
    sub_obj.plan = "free"
    sub_obj.status = "trialing"
    sub_obj.current_period_start = datetime.now(UTC)
    sub_obj.current_period_end = datetime.now(UTC) + timedelta(days=14)
    sub_obj.trial_ends_at = datetime.now(UTC) + timedelta(days=14)
    sub_obj.cancelled_at = None
    sub_obj.created_at = datetime.now(UTC)

    none_result = MagicMock()
    none_result.scalar_one_or_none.return_value = None

    create_calls = [0]

    async def _execute(stmt, **_kw):  # type: ignore[no-untyped-def]
        create_calls[0] += 1
        if create_calls[0] == 1:
            return none_result
        return none_result

    mock_session.execute.side_effect = _execute

    mock_session.add.side_effect = lambda obj: setattr(obj, "__dict__", {})

    service = SaasService(mock_session)

    # Mock the internal create calls via flush
    with (
        patch.object(service._tenants, "create", return_value=tenant_obj),
        patch.object(service._subscriptions, "create", return_value=sub_obj),
        patch.object(service._tenants, "get_by_slug", return_value=None),
    ):
        tenant_read, sub_read = await service.create_tenant(
            TenantCreate(name="Acme", slug="acme-new", plan="free")
        )

    assert tenant_read.slug == "acme-new"
    assert sub_read.status == "trialing"


# ── Service: API key returned once, then only hash stored ─────────────────────


async def test_create_api_key_returns_raw_key_once(mock_session: AsyncMock) -> None:
    raw_key_seen: list[str] = []
    key_hash_seen: list[str] = []

    async def _fake_create(
        *,
        tenant_id: UUID,
        name: str,
        key_prefix: str,
        key_hash: str,
        project_id: UUID | None = None,
        scopes_json: str | None = None,
        expires_at: datetime | None = None,
    ) -> ApiKey:
        key_hash_seen.append(key_hash)
        key = MagicMock(spec=ApiKey)
        key.id = uuid4()
        key.tenant_id = tenant_id
        key.project_id = project_id
        key.name = name
        key.key_prefix = key_prefix
        key.scopes = scopes_json
        key.expires_at = expires_at
        key.last_used_at = None
        key.revoked_at = None
        key.is_active = True
        key.created_at = datetime.now(UTC)
        return key

    service = SaasService(mock_session)
    tid = uuid4()

    with patch.object(service._keys, "create", side_effect=_fake_create):
        result = await service.create_api_key(
            tid, ApiKeyCreate(name="CI key", scopes=["read"])
        )

    # The ApiKeyCreated schema contains the raw key
    assert isinstance(result, ApiKeyCreated)
    assert result.raw_key.startswith("aegis_live_")
    raw_key_seen.append(result.raw_key)

    # The stored hash matches the raw key
    assert len(key_hash_seen) == 1
    assert key_hash_seen[0] == hash_api_key(raw_key_seen[0])

    # Subsequent ApiKeyRead (non-created) has no raw_key attribute
    read_fields = ApiKeyRead.model_fields
    assert "raw_key" not in read_fields


async def test_verify_api_key_returns_none_for_unknown_hash(
    mock_session: AsyncMock,
) -> None:
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result_mock

    service = SaasService(mock_session)
    result = await service.verify_api_key("unknown-key")
    assert result is None


async def test_verify_api_key_returns_none_for_revoked_key(
    mock_session: AsyncMock,
) -> None:
    revoked_key = MagicMock(spec=ApiKey)
    revoked_key.is_active = False

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = revoked_key
    mock_session.execute.return_value = result_mock

    service = SaasService(mock_session)
    result = await service.verify_api_key("aegis_live_some_revoked_key")
    assert result is None


# ── Service: SQL Airlock event hashes raw query ───────────────────────────────


async def test_persist_sql_airlock_event_hashes_raw_query(
    mock_session: AsyncMock,
) -> None:
    stored_fp: list[str | None] = []

    async def _fake_persist(
        *,
        tenant_id: UUID,
        project_id: UUID | None,
        actor_id: UUID | None,
        action: str,
        blocked_at_stage: str | None,
        block_reason: str | None,
        query_fingerprint: str | None,
        duration_ms: int | None,
        rows_returned: int | None,
    ) -> SqlAirlockEvent:
        stored_fp.append(query_fingerprint)
        event = MagicMock(spec=SqlAirlockEvent)
        event.id = uuid4()
        event.tenant_id = tenant_id
        event.project_id = project_id
        event.actor_id = actor_id
        event.action = action
        event.blocked_at_stage = blocked_at_stage
        event.block_reason = block_reason
        event.query_fingerprint = query_fingerprint
        event.duration_ms = duration_ms
        event.rows_returned = rows_returned
        event.created_at = datetime.now(UTC)
        return event

    service = SaasService(mock_session)
    raw_sql = "SELECT * FROM users WHERE role = 'admin'"
    tid = uuid4()

    with patch.object(
        service._events, "persist_sql_airlock_event", side_effect=_fake_persist
    ):
        result = await service.persist_sql_airlock_event(
            tid,
            SqlAirlockEventCreate(
                action="block",
                raw_query=raw_sql,
            ),
        )

    # Raw SQL is not in the result
    assert raw_sql not in (result.query_fingerprint or "")
    # Fingerprint is sha256 of raw SQL
    assert stored_fp[0] == fingerprint_query(raw_sql)


# ── Service: security event sanitizes detail ──────────────────────────────────


async def test_persist_security_event_sanitizes_jwt_in_detail(
    mock_session: AsyncMock,
) -> None:
    stored_detail: list[str | None] = []

    async def _fake_persist(
        *,
        tenant_id: UUID,
        event_type: str,
        severity: str,
        actor_id: UUID | None = None,
        ip_address: str | None = None,
        detail: str | None = None,
    ) -> SecurityEvent:
        stored_detail.append(detail)
        event = MagicMock(spec=SecurityEvent)
        event.id = uuid4()
        event.tenant_id = tenant_id
        event.event_type = event_type
        event.severity = severity
        event.actor_id = actor_id
        event.ip_address = ip_address
        event.detail = detail
        event.resolved_at = None
        event.created_at = datetime.now(UTC)
        return event

    jwt = (
        "eyJhbGciOiJIUzI1NiJ9"
        ".eyJzdWIiOiJ1c2VyMTIzIn0"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    service = SaasService(mock_session)

    with patch.object(
        service._events, "persist_security_event", side_effect=_fake_persist
    ):
        await service.persist_security_event(
            uuid4(),
            SecurityEventCreate(
                event_type="jwt_failure",
                severity="warning",
                detail=f"Invalid token: {jwt}",
            ),
        )

    assert stored_detail[0] is not None
    # Sanitize may apply multiple passes; raw JWT must be absent regardless of marker.
    assert "eyJzdWIiOiJ1c2VyMTIzIn0" not in stored_detail[0]
    assert "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" not in stored_detail[0]


# ── Service: audit event drops sensitive extra keys ───────────────────────────


async def test_persist_audit_event_drops_sensitive_extra_keys(
    mock_session: AsyncMock,
) -> None:
    stored_extra: list[str | None] = []

    async def _fake_persist(
        *,
        tenant_id: UUID,
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
        stored_extra.append(extra_json)
        event = MagicMock(spec=AuditEvent)
        event.id = uuid4()
        event.tenant_id = tenant_id
        event.actor_id = actor_id
        event.actor_type = actor_type
        event.action = action
        event.resource_type = resource_type
        event.resource_id = resource_id
        event.ip_address = ip_address
        event.outcome = outcome
        event.created_at = datetime.now(UTC)
        return event

    service = SaasService(mock_session)

    with patch.object(
        service._events, "persist_audit_event", side_effect=_fake_persist
    ):
        await service.persist_audit_event(
            uuid4(),
            AuditEventCreate(
                action="api_call",
                extra={"password": "s3cr3t", "endpoint": "/query"},
            ),
        )

    assert stored_extra[0] is not None
    parsed = json.loads(stored_extra[0])
    assert "password" not in parsed
    assert "endpoint" in parsed


# ── Usage record increments ───────────────────────────────────────────────────


async def test_usage_repo_increment_calls_get_or_create(
    usage_repo: UsageRepository, mock_session: AsyncMock
) -> None:
    existing = MagicMock(spec=UsageRecord)
    existing.request_count = 5
    existing.ai_call_count = 0
    existing.sql_airlock_blocks = 0
    existing.rate_limit_blocks = 0
    existing.token_usage = 0

    with patch.object(usage_repo, "get_or_create", return_value=existing):
        await usage_repo.increment(
            tenant_id=uuid4(),
            billing_period="2026-06",
            request_count=3,
        )
    assert existing.request_count == 8


# ── Backup scripts contain strict mode ───────────────────────────────────────


_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"


def test_backup_script_has_strict_mode() -> None:
    script = _SCRIPTS_DIR / "backup_postgres.sh"
    assert script.exists(), "backup_postgres.sh must exist"
    content = script.read_text()
    assert "set -euo pipefail" in content


def test_restore_script_has_strict_mode() -> None:
    script = _SCRIPTS_DIR / "restore_postgres.sh"
    assert script.exists(), "restore_postgres.sh must exist"
    content = script.read_text()
    assert "set -euo pipefail" in content


def test_verify_restore_script_has_strict_mode() -> None:
    script = _SCRIPTS_DIR / "verify_restore.sh"
    assert script.exists(), "verify_restore.sh must exist"
    content = script.read_text()
    assert "set -euo pipefail" in content


def test_backup_script_does_not_print_password() -> None:
    script = _SCRIPTS_DIR / "backup_postgres.sh"
    content = script.read_text()
    # Must not echo raw password variable to stdout
    assert 'echo "$PGPASSWORD"' not in content
    assert "echo $PGPASSWORD" not in content


def test_backup_script_uses_pg_dump() -> None:
    script = _SCRIPTS_DIR / "backup_postgres.sh"
    content = script.read_text()
    assert "pg_dump" in content


def test_backup_script_keeps_last_7() -> None:
    script = _SCRIPTS_DIR / "backup_postgres.sh"
    content = script.read_text()
    assert "7" in content


def test_restore_script_does_not_print_password() -> None:
    script = _SCRIPTS_DIR / "restore_postgres.sh"
    content = script.read_text()
    assert 'echo "$PGPASSWORD"' not in content
    assert "echo $PGPASSWORD" not in content
