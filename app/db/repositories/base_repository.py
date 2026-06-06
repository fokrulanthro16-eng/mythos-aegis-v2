from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TenantIsolationError
from app.db.base import Base
from app.db.models.order import Order
from app.db.models.product import Product
from app.db.models.user import User


class BaseRepository[M: Base]:
    def __init__(self, session: AsyncSession, model: type[M]) -> None:
        self._session = session
        self._model = model

    def _require_tenant(self, tenant_id: UUID | None) -> UUID:
        if tenant_id is None:
            raise TenantIsolationError(
                f"{self._model.__name__} queries require tenant_id"
            )
        return tenant_id

    async def get_by_id(self, entity_id: UUID, *, tenant_id: UUID | None) -> M | None:
        tid = self._require_tenant(tenant_id)
        stmt = select(self._model).where(
            self._model.id == entity_id,  # type: ignore[attr-defined]
            self._model.tenant_id == tid,  # type: ignore[attr-defined]
            self._model.deleted_at.is_(None),  # type: ignore[attr-defined]
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_tenant(self, tenant_id: UUID | None) -> list[M]:
        tid = self._require_tenant(tenant_id)
        stmt = select(self._model).where(
            self._model.tenant_id == tid,  # type: ignore[attr-defined]
            self._model.deleted_at.is_(None),  # type: ignore[attr-defined]
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, *, tenant_id: UUID | None, **kwargs: Any) -> M:
        tid = self._require_tenant(tenant_id)
        instance: M = self._model(tenant_id=tid, **kwargs)
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def update(
        self,
        entity_id: UUID,
        *,
        tenant_id: UUID | None,
        **kwargs: Any,
    ) -> M | None:
        instance = await self.get_by_id(entity_id, tenant_id=tenant_id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self._session.flush()
        return instance

    async def soft_delete(self, entity_id: UUID, *, tenant_id: UUID | None) -> bool:
        instance = await self.get_by_id(entity_id, tenant_id=tenant_id)
        if instance is None:
            return False
        instance.deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
        await self._session.flush()
        return True


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Product)


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Order)
