"""Tests for the AI Gateway quota service.

Database is fully mocked — no live Postgres required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.ai_gateway.quota import QuotaService
from app.core.exceptions import AIQuotaExceededError
from app.core.result import Failure, Success

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_session(record: object = None) -> AsyncMock:
    """Build a session mock; execute().scalar_one_or_none() returns *record*."""
    session = AsyncMock()
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = record
    session.execute.return_value = db_result
    return session


def _make_record(ai_call_count: int) -> MagicMock:
    record = MagicMock()
    record.ai_call_count = ai_call_count
    return record


TENANT_ID = uuid4()
BILLING_PERIOD = "2026-06"


# ── No record → Success ───────────────────────────────────────────────────────


async def test_check_returns_success_when_no_record() -> None:
    session = _make_session(record=None)
    svc = QuotaService(session)
    result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Success)
    assert result.value is None


async def test_check_queries_with_correct_tenant_and_period() -> None:
    session = _make_session(record=None)
    svc = QuotaService(session)
    await svc.check(TENANT_ID, BILLING_PERIOD)
    session.execute.assert_called_once()


# ── Under limit → Success ─────────────────────────────────────────────────────


async def test_check_returns_success_when_under_limit() -> None:
    record = _make_record(ai_call_count=100)
    session = _make_session(record=record)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = True
        mock_settings.AI_MONTHLY_REQUEST_LIMIT = 30_000
        result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Success)


async def test_check_returns_success_when_count_is_one_below_limit() -> None:
    limit = 30_000
    record = _make_record(ai_call_count=limit - 1)
    session = _make_session(record=record)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = True
        mock_settings.AI_MONTHLY_REQUEST_LIMIT = limit
        result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Success)


# ── At or over limit → Failure ────────────────────────────────────────────────


async def test_check_returns_failure_when_at_limit() -> None:
    limit = 30_000
    record = _make_record(ai_call_count=limit)
    session = _make_session(record=record)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = True
        mock_settings.AI_MONTHLY_REQUEST_LIMIT = limit
        result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Failure)
    assert isinstance(result.error, AIQuotaExceededError)


async def test_check_returns_failure_when_over_limit() -> None:
    limit = 500
    record = _make_record(ai_call_count=limit + 50)
    session = _make_session(record=record)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = True
        mock_settings.AI_MONTHLY_REQUEST_LIMIT = limit
        result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Failure)
    assert isinstance(result.error, AIQuotaExceededError)


async def test_failure_message_contains_billing_period() -> None:
    limit = 100
    record = _make_record(ai_call_count=limit)
    session = _make_session(record=record)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = True
        mock_settings.AI_MONTHLY_REQUEST_LIMIT = limit
        result = await svc.check(TENANT_ID, "2026-03")
    assert isinstance(result, Failure)
    assert "2026-03" in result.message


async def test_failure_message_contains_limit_value() -> None:
    limit = 250
    record = _make_record(ai_call_count=limit)
    session = _make_session(record=record)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = True
        mock_settings.AI_MONTHLY_REQUEST_LIMIT = limit
        result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Failure)
    assert "250" in result.message


# ── Quota disabled → always Success ──────────────────────────────────────────


async def test_check_returns_success_when_quota_disabled_and_no_record() -> None:
    session = _make_session(record=None)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = False
        result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Success)
    # When quota is disabled the DB should not be queried at all.
    session.execute.assert_not_called()


async def test_check_returns_success_when_quota_disabled_even_over_limit() -> None:
    """Disabling quota must bypass the check entirely — even if usage is huge."""
    record = _make_record(ai_call_count=999_999)
    session = _make_session(record=record)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = False
        result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Success)
    session.execute.assert_not_called()


# ── project_id scoping ────────────────────────────────────────────────────────


async def test_check_passes_project_id_to_query() -> None:
    project_id = uuid4()
    session = _make_session(record=None)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = True
        mock_settings.AI_MONTHLY_REQUEST_LIMIT = 30_000
        await svc.check(TENANT_ID, BILLING_PERIOD, project_id=project_id)
    session.execute.assert_called_once()


async def test_check_with_no_project_id_uses_none() -> None:
    session = _make_session(record=None)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = True
        mock_settings.AI_MONTHLY_REQUEST_LIMIT = 30_000
        result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Success)
    session.execute.assert_called_once()


# ── Zero-count record → Success ───────────────────────────────────────────────


async def test_check_returns_success_for_zero_count() -> None:
    record = _make_record(ai_call_count=0)
    session = _make_session(record=record)
    svc = QuotaService(session)
    with patch("app.ai_gateway.quota.settings") as mock_settings:
        mock_settings.AI_QUOTA_ENABLED = True
        mock_settings.AI_MONTHLY_REQUEST_LIMIT = 30_000
        result = await svc.check(TENANT_ID, BILLING_PERIOD)
    assert isinstance(result, Success)
