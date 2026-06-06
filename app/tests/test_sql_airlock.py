"""SQL Airlock Guardrail Core — behavioural test suite.

All tests are isolated; no real database required.
"""

import types
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import sqlglot
from sqlglot import exp

from app.core.exceptions import SqlAirlockViolation
from app.core.result import Failure, Success
from app.pathways.sql_airlock.executor import _TIMEOUT_SECONDS, execute_analytics
from app.pathways.sql_airlock.rewriter import (
    enforce_limit,
    inject_tenant_filter,
    rewrite,
)
from app.pathways.sql_airlock.schemas import AnalyticsRequest
from app.pathways.sql_airlock.service import execute_analytics_query
from app.pathways.sql_airlock.validator import validate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(sql: str) -> exp.Select:
    return sqlglot.parse_one(sql)  # type: ignore[return-value]


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    rows: list[dict[str, object]] = [{"id": "abc123", "email": "user@example.com"}]
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = rows
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mappings
    session.execute.return_value = mock_result
    return session


# ---------------------------------------------------------------------------
# Rule 1 — SELECT ONLY
# ---------------------------------------------------------------------------


def test_drop_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="Only SELECT"):
        validate("DROP TABLE users")


def test_delete_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="Only SELECT"):
        validate("DELETE FROM users WHERE id = 1")


def test_update_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="Only SELECT"):
        validate("UPDATE users SET email = 'x' WHERE id = 1")


# ---------------------------------------------------------------------------
# Rule 2 — TABLE WHITELIST
# ---------------------------------------------------------------------------


def test_unknown_table_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="not in the allowed registry"):
        validate("SELECT id FROM shadow_accounts")


# ---------------------------------------------------------------------------
# Rule 3 — COLUMN MASKING
# ---------------------------------------------------------------------------


def test_select_star_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="SELECT \\* is not allowed"):
        validate("SELECT * FROM users")


def test_blocked_column_password_hash_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="not permitted"):
        validate("SELECT id, password_hash FROM users")


def test_blocked_column_api_token_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="not permitted"):
        validate("SELECT id, api_token FROM users")


# ---------------------------------------------------------------------------
# Rule 5 — TEMPORAL BOUNDARY
# ---------------------------------------------------------------------------


def test_90_day_rule_enforced() -> None:
    sql = (
        "SELECT id FROM orders "
        "WHERE created_at > '2024-01-01' AND created_at < '2024-06-01'"
    )
    with pytest.raises(SqlAirlockViolation, match="90-day maximum"):
        validate(sql)


def test_dates_within_90_days_accepted() -> None:
    sql = (
        "SELECT id FROM orders "
        "WHERE created_at > '2024-01-01' AND created_at < '2024-03-15'"
    )
    result = validate(sql)
    assert isinstance(result, exp.Select)


# ---------------------------------------------------------------------------
# Rule 7 — LEXICAL SANITIZATION
# ---------------------------------------------------------------------------


def test_comment_injection_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="Forbidden pattern"):
        validate("SELECT id FROM users -- comment")


def test_block_comment_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="Forbidden pattern"):
        validate("SELECT id FROM users /* comment */ WHERE id = 1")


def test_semicolon_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="Forbidden pattern"):
        validate("SELECT id FROM users; DROP TABLE users")


def test_null_byte_rejected() -> None:
    with pytest.raises(SqlAirlockViolation, match="Forbidden pattern"):
        validate("SELECT id FROM users WHERE id = '\x00'")


# ---------------------------------------------------------------------------
# Rule 4 — TENANT FILTER INJECTION
# ---------------------------------------------------------------------------


def test_tenant_filter_injected_no_where() -> None:
    """When no WHERE clause, user_id = :session_user_id is added."""
    select = _parse("SELECT id FROM users")
    result = inject_tenant_filter(select)
    sql_out = result.sql()
    assert "session_user_id" in sql_out
    assert "WHERE" in sql_out.upper()


def test_tenant_filter_injected_preserves_existing_predicates() -> None:
    """Existing WHERE predicates are preserved alongside the injected filter."""
    select = _parse("SELECT id FROM orders WHERE status = 'PENDING'")
    result = inject_tenant_filter(select)
    sql_out = result.sql()
    assert "session_user_id" in sql_out
    assert "status" in sql_out


def test_tenant_filter_replaces_user_supplied_predicate() -> None:
    """A user-supplied user_id predicate is removed and replaced."""
    select = _parse("SELECT id FROM users WHERE user_id = 999")
    result = inject_tenant_filter(select)
    sql_out = result.sql()
    assert "999" not in sql_out
    assert "session_user_id" in sql_out


# ---------------------------------------------------------------------------
# Rule 6 — RESOURCE PROTECTION (LIMIT)
# ---------------------------------------------------------------------------


def test_limit_added_when_missing() -> None:
    select = _parse("SELECT id FROM users")
    result = enforce_limit(select)
    assert "100" in result.sql()


def test_limit_reduced_when_over_100() -> None:
    select = _parse("SELECT id FROM users LIMIT 500")
    result = enforce_limit(select)
    sql_out = result.sql()
    assert "100" in sql_out
    assert "500" not in sql_out


def test_limit_preserved_when_under_100() -> None:
    select = _parse("SELECT id FROM users LIMIT 10")
    result = enforce_limit(select)
    assert "10" in result.sql()


# ---------------------------------------------------------------------------
# Rule 8 — AST STRUCTURAL VALIDATION (reparse)
# ---------------------------------------------------------------------------


def test_reparse_succeeds_after_rewrite() -> None:
    """The rewritten SQL must be valid SQL that sqlglot can reparse."""
    select = _parse("SELECT id, email FROM users")
    rewritten = rewrite(select)
    reparsed = sqlglot.parse_one(rewritten)
    assert isinstance(reparsed, exp.Select)


# ---------------------------------------------------------------------------
# Executor — timeout configuration and behaviour
# ---------------------------------------------------------------------------


def test_timeout_configured() -> None:
    assert _TIMEOUT_SECONDS == 3.0


async def test_executor_timeout_returns_failure() -> None:
    """A TimeoutError from wait_for surfaces as Failure, not a raised exception."""

    async def _simulate_timeout(coro: object, *_: object, **__: object) -> object:
        if isinstance(coro, types.CoroutineType):
            coro.close()
        raise TimeoutError()

    mock = AsyncMock()

    with patch("asyncio.wait_for", _simulate_timeout):
        result = await execute_analytics(
            "SELECT id FROM users WHERE user_id = :session_user_id LIMIT 100",
            session_user_id=uuid4(),
            session=mock,
        )

    assert isinstance(result, Failure)
    assert isinstance(result.error, SqlAirlockViolation)
    assert "exceeded" in result.message.lower()


# ---------------------------------------------------------------------------
# Service — end-to-end with mocked session
# ---------------------------------------------------------------------------


async def test_safe_result_returned(mock_session: AsyncMock) -> None:
    """Valid query flows through the full pipeline and returns Success."""
    request = AnalyticsRequest(
        sql="SELECT id, email FROM users",
        user_id=uuid4(),
    )
    result = await execute_analytics_query(request, mock_session)

    assert isinstance(result, Success)
    assert result.value.row_count == 1
    assert result.value.rows[0]["id"] == "abc123"


async def test_airlock_violation_returns_failure_not_exception(
    mock_session: AsyncMock,
) -> None:
    """SqlAirlockViolation surfaces as Failure; DB is never touched."""
    request = AnalyticsRequest(
        sql="DROP TABLE users",
        user_id=uuid4(),
    )
    result = await execute_analytics_query(request, mock_session)

    assert isinstance(result, Failure)
    assert isinstance(result.error, SqlAirlockViolation)
    mock_session.execute.assert_not_called()
