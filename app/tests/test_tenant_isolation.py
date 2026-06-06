from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import TenantIsolationError
from app.db.repositories.base_repository import (
    OrderRepository,
    ProductRepository,
    UserRepository,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    return session


@pytest.fixture
def user_repo(mock_session: AsyncMock) -> UserRepository:
    return UserRepository(mock_session)


@pytest.fixture
def product_repo(mock_session: AsyncMock) -> ProductRepository:
    return ProductRepository(mock_session)


@pytest.fixture
def order_repo(mock_session: AsyncMock) -> OrderRepository:
    return OrderRepository(mock_session)


# ---------------------------------------------------------------------------
# get_by_id – tenant guard
# ---------------------------------------------------------------------------


async def test_get_by_id_raises_without_tenant(user_repo: UserRepository) -> None:
    with pytest.raises(TenantIsolationError):
        await user_repo.get_by_id(uuid4(), tenant_id=None)


async def test_get_by_id_product_raises_without_tenant(
    product_repo: ProductRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await product_repo.get_by_id(uuid4(), tenant_id=None)


async def test_get_by_id_order_raises_without_tenant(
    order_repo: OrderRepository,
) -> None:
    with pytest.raises(TenantIsolationError):
        await order_repo.get_by_id(uuid4(), tenant_id=None)


async def test_get_by_id_with_valid_tenant_executes_query(
    user_repo: UserRepository, mock_session: AsyncMock
) -> None:
    await user_repo.get_by_id(uuid4(), tenant_id=uuid4())
    assert mock_session.execute.called


# ---------------------------------------------------------------------------
# list_for_tenant – tenant guard
# ---------------------------------------------------------------------------


async def test_list_for_tenant_raises_without_tenant(user_repo: UserRepository) -> None:
    with pytest.raises(TenantIsolationError):
        await user_repo.list_for_tenant(None)


async def test_list_for_tenant_returns_empty_list(user_repo: UserRepository) -> None:
    result = await user_repo.list_for_tenant(uuid4())
    assert result == []


# ---------------------------------------------------------------------------
# create – tenant guard
# ---------------------------------------------------------------------------


async def test_create_raises_without_tenant(user_repo: UserRepository) -> None:
    with pytest.raises(TenantIsolationError):
        await user_repo.create(tenant_id=None, email="x@x.com")


# ---------------------------------------------------------------------------
# update – tenant guard
# ---------------------------------------------------------------------------


async def test_update_raises_without_tenant(user_repo: UserRepository) -> None:
    with pytest.raises(TenantIsolationError):
        await user_repo.update(uuid4(), tenant_id=None, email="new@x.com")


async def test_update_returns_none_when_not_found(user_repo: UserRepository) -> None:
    result = await user_repo.update(uuid4(), tenant_id=uuid4(), email="x@x.com")
    assert result is None


# ---------------------------------------------------------------------------
# soft_delete – tenant guard + behavior
# ---------------------------------------------------------------------------


async def test_soft_delete_raises_without_tenant(user_repo: UserRepository) -> None:
    with pytest.raises(TenantIsolationError):
        await user_repo.soft_delete(uuid4(), tenant_id=None)


async def test_soft_delete_returns_false_when_not_found(
    user_repo: UserRepository,
) -> None:
    result = await user_repo.soft_delete(uuid4(), tenant_id=uuid4())
    assert result is False


async def test_soft_delete_sets_deleted_at_on_found_entity(
    mock_session: AsyncMock,
) -> None:
    from datetime import datetime
    from unittest.mock import MagicMock

    entity = MagicMock()
    entity.deleted_at = None

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = entity
    mock_session.execute.return_value = result_mock

    repo = UserRepository(mock_session)
    deleted = await repo.soft_delete(uuid4(), tenant_id=uuid4())

    assert deleted is True
    assert entity.deleted_at is not None
    assert isinstance(entity.deleted_at, datetime)


# ---------------------------------------------------------------------------
# TenantIsolationError carries message
# ---------------------------------------------------------------------------


async def test_tenant_isolation_error_message(user_repo: UserRepository) -> None:
    with pytest.raises(TenantIsolationError, match="tenant_id"):
        await user_repo.get_by_id(uuid4(), tenant_id=None)


# ---------------------------------------------------------------------------
# Multiple repositories enforce isolation independently
# ---------------------------------------------------------------------------


async def test_all_repos_enforce_isolation(
    user_repo: UserRepository,
    product_repo: ProductRepository,
    order_repo: OrderRepository,
) -> None:
    eid = uuid4()
    for repo in (user_repo, product_repo, order_repo):
        with pytest.raises(TenantIsolationError):
            await repo.get_by_id(eid, tenant_id=None)
