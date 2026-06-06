from uuid import UUID

from sqlalchemy import select

from app.db.models.order import Order
from app.db.repositories.base_repository import OrderRepository


class WriteOrderRepository(OrderRepository):
    """Extends the base order repository with a 3-key lookup that enforces
    ownership at the database level: order_id + tenant_id + user_id must all
    match. Never queries by order_id alone."""

    async def get_for_cancellation(
        self,
        order_id: UUID,
        *,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Order | None:
        stmt = select(Order).where(
            Order.id == order_id,
            Order.tenant_id == tenant_id,
            Order.user_id == user_id,
            Order.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
