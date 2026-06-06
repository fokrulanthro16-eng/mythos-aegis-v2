"""Pathway A – CANCEL_ORDER lifecycle tests.

Twelve behavioural cases, each isolated with a mocked async session and
a lightweight spy MFA provider.  No real database is required.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleViolation,
    DatabaseError,
    TenantIsolationError,
)
from app.core.result import Failure, Success
from app.core.security_context import SecurityContext
from app.db.models.order import OrderStatus
from app.pathways.write.lifecycle import AuditRecord, build_audit_record
from app.pathways.write.mfa import MockMFAProvider
from app.pathways.write.repository import WriteOrderRepository
from app.pathways.write.schemas import CancelOrderRequest
from app.pathways.write.service import execute_cancel_order

# ---------------------------------------------------------------------------
# Spy MFA provider – lets tests verify the hook was invoked
# ---------------------------------------------------------------------------


class SpyMFAProvider(MockMFAProvider):
    def __init__(self) -> None:
        self.challenge_requested = False
        self.challenge_verified = False

    async def request_challenge(self, user_id: UUID, tenant_id: UUID) -> str:
        self.challenge_requested = True
        return await super().request_challenge(user_id, tenant_id)

    async def verify_challenge(self, user_id: UUID, challenge_token: str) -> bool:
        self.challenge_verified = True
        return await super().verify_challenge(user_id, challenge_token)


# ---------------------------------------------------------------------------
# Shared factories
# ---------------------------------------------------------------------------


def _make_ctx(
    *,
    user_id: UUID | None = None,
    tenant_id: UUID | None = None,
) -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=user_id or uuid4(),
        tenant_id=tenant_id or uuid4(),
        roles=frozenset(),
        permissions=frozenset(),
    )


def _make_order(
    *,
    user_id: UUID,
    tenant_id: UUID,
    status: OrderStatus = OrderStatus.PENDING,
    cancellable_until: datetime | None = None,
) -> MagicMock:
    order = MagicMock()
    order.user_id = user_id
    order.tenant_id = tenant_id
    order.status = status
    order.cancellable_until = (
        cancellable_until
        if cancellable_until is not None
        else datetime.now(UTC) + timedelta(hours=24)
    )
    return order


def _wire_session(mock_session: AsyncMock, order: MagicMock | None) -> None:
    """Point session.execute() at a result that returns *order*."""
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = order
    mock_session.execute.return_value = db_result


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    # session.begin() must return an async context manager, not a coroutine.
    # AsyncMock attributes are themselves AsyncMocks, so calling session.begin()
    # returns a coroutine rather than the context manager the service expects.
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)
    # Default: no order found
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = None
    session.execute.return_value = db_result
    return session


@pytest.fixture
def spy_mfa() -> SpyMFAProvider:
    return SpyMFAProvider()


# ---------------------------------------------------------------------------
# 1. Valid cancellation succeeds
# ---------------------------------------------------------------------------


async def test_valid_cancellation_succeeds(mock_session: AsyncMock) -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    order_id = uuid4()

    order = _make_order(user_id=user_id, tenant_id=tenant_id)
    _wire_session(mock_session, order)

    ctx = _make_ctx(user_id=user_id, tenant_id=tenant_id)
    request = CancelOrderRequest(order_id=order_id)

    result = await execute_cancel_order(request, ctx, mock_session, MockMFAProvider())

    assert isinstance(result, Success)
    assert result.value.operation_status == "cancelled"
    assert result.value.order_id == order_id
    assert isinstance(result.value.cancelled_at, datetime)


# ---------------------------------------------------------------------------
# 2. Already-cancelled order fails
# ---------------------------------------------------------------------------


async def test_cancelled_order_fails(mock_session: AsyncMock) -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    order = _make_order(
        user_id=user_id, tenant_id=tenant_id, status=OrderStatus.CANCELLED
    )
    _wire_session(mock_session, order)

    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        _make_ctx(user_id=user_id, tenant_id=tenant_id),
        mock_session,
        MockMFAProvider(),
    )

    assert isinstance(result, Failure)
    assert isinstance(result.error, BusinessRuleViolation)


# ---------------------------------------------------------------------------
# 3. Shipped order fails
# ---------------------------------------------------------------------------


async def test_shipped_order_fails(mock_session: AsyncMock) -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    order = _make_order(
        user_id=user_id, tenant_id=tenant_id, status=OrderStatus.SHIPPED
    )
    _wire_session(mock_session, order)

    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        _make_ctx(user_id=user_id, tenant_id=tenant_id),
        mock_session,
        MockMFAProvider(),
    )

    assert isinstance(result, Failure)
    assert isinstance(result.error, BusinessRuleViolation)


# ---------------------------------------------------------------------------
# 4. Expired cancellation window fails
# ---------------------------------------------------------------------------


async def test_expired_cancellation_window_fails(mock_session: AsyncMock) -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    order = _make_order(
        user_id=user_id,
        tenant_id=tenant_id,
        status=OrderStatus.PENDING,
        cancellable_until=datetime.now(UTC) - timedelta(minutes=1),
    )
    _wire_session(mock_session, order)

    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        _make_ctx(user_id=user_id, tenant_id=tenant_id),
        mock_session,
        MockMFAProvider(),
    )

    assert isinstance(result, Failure)
    assert isinstance(result.error, BusinessRuleViolation)
    assert "expired" in result.message.lower()


# ---------------------------------------------------------------------------
# 5. Missing tenant rejected
# ---------------------------------------------------------------------------


async def test_missing_tenant_rejected(mock_session: AsyncMock) -> None:
    ctx = _make_ctx(tenant_id=UUID(int=0))  # nil sentinel

    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        ctx,
        mock_session,
        MockMFAProvider(),
    )

    assert isinstance(result, Failure)
    assert isinstance(result.error, TenantIsolationError)
    # Database must never be touched
    mock_session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Missing user rejected
# ---------------------------------------------------------------------------


async def test_missing_user_rejected(mock_session: AsyncMock) -> None:
    ctx = _make_ctx(user_id=UUID(int=0))  # nil sentinel

    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        ctx,
        mock_session,
        MockMFAProvider(),
    )

    assert isinstance(result, Failure)
    assert isinstance(result.error, AuthorizationError)
    mock_session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# 7. Ownership mismatch returns generic safe failure
# ---------------------------------------------------------------------------


async def test_ownership_mismatch_blocked(mock_session: AsyncMock) -> None:
    # Repository returns None because the user_id filter excluded the row
    _wire_session(mock_session, None)

    ctx = _make_ctx()
    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        ctx,
        mock_session,
        MockMFAProvider(),
    )

    assert isinstance(result, Failure)
    assert isinstance(result.error, AuthorizationError)
    # Message must not reveal whether the order exists
    assert (
        "not found" in result.message.lower()
        or "not authorized" in result.message.lower()
    )


# ---------------------------------------------------------------------------
# 8. Transaction rollback on unexpected error
# ---------------------------------------------------------------------------


async def test_transaction_rollback_on_db_error(mock_session: AsyncMock) -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    order = _make_order(user_id=user_id, tenant_id=tenant_id)
    _wire_session(mock_session, order)

    # Simulate a database error during flush
    from sqlalchemy.exc import SQLAlchemyError

    mock_session.flush.side_effect = SQLAlchemyError("connection lost")

    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        _make_ctx(user_id=user_id, tenant_id=tenant_id),
        mock_session,
        MockMFAProvider(),
    )

    assert isinstance(result, Failure)
    assert isinstance(result.error, DatabaseError)
    # No explicit commit should have been made
    mock_session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# 9. MFA hook is called on every valid cancellation
# ---------------------------------------------------------------------------


async def test_mfa_hook_called(
    mock_session: AsyncMock, spy_mfa: SpyMFAProvider
) -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    order = _make_order(user_id=user_id, tenant_id=tenant_id)
    _wire_session(mock_session, order)

    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        _make_ctx(user_id=user_id, tenant_id=tenant_id),
        mock_session,
        spy_mfa,
    )

    assert isinstance(result, Success)
    assert spy_mfa.challenge_requested, "request_challenge() was not called"
    assert spy_mfa.challenge_verified, "verify_challenge() was not called"


# ---------------------------------------------------------------------------
# 10. Audit record carries all required fields (no secrets)
# ---------------------------------------------------------------------------


def test_audit_payload_created() -> None:
    request_id = uuid4()
    tenant_id = uuid4()
    user_id = uuid4()
    order_id = uuid4()

    record = build_audit_record(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        order_id=order_id,
        action="CANCEL_ORDER",
    )

    assert isinstance(record, AuditRecord)
    assert record.request_id == request_id
    assert record.tenant_id == tenant_id
    assert record.user_id == user_id
    assert record.order_id == order_id
    assert record.action == "CANCEL_ORDER"
    assert isinstance(record.timestamp, datetime)
    # Verify no secret-looking fields exist
    assert not hasattr(record, "password")
    assert not hasattr(record, "token")
    assert not hasattr(record, "secret")


# ---------------------------------------------------------------------------
# 11. Raw exceptions never escape the service boundary
# ---------------------------------------------------------------------------


async def test_no_raw_exception_leakage(mock_session: AsyncMock) -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    # Corrupt the session so an unexpected error fires deep inside
    mock_session.execute.side_effect = RuntimeError("internal explosion")

    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        _make_ctx(user_id=user_id, tenant_id=tenant_id),
        mock_session,
        MockMFAProvider(),
    )

    # Must return Failure, never raise
    assert isinstance(result, Failure)
    # Must not expose the raw exception message
    assert "internal explosion" not in result.message


# ---------------------------------------------------------------------------
# 12. Repository refuses to query without tenant_id in context
# ---------------------------------------------------------------------------


async def test_repository_never_queries_without_tenant(
    mock_session: AsyncMock,
) -> None:
    # Nil tenant triggers TenantIsolationError before repository is touched
    ctx = _make_ctx(tenant_id=UUID(int=0))

    result = await execute_cancel_order(
        CancelOrderRequest(order_id=uuid4()),
        ctx,
        mock_session,
        MockMFAProvider(),
    )

    assert isinstance(result, Failure)
    assert isinstance(result.error, TenantIsolationError)
    mock_session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Bonus: WriteOrderRepository directly refuses tenant=None
# ---------------------------------------------------------------------------


async def test_write_repository_guard_is_independent(mock_session: AsyncMock) -> None:
    """Even if the service guard is bypassed, the base repo blocks nil tenant."""
    repo = WriteOrderRepository(mock_session)

    with pytest.raises(TenantIsolationError):
        await repo.get_by_id(uuid4(), tenant_id=None)
