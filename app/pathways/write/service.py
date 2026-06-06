import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleViolation,
    DatabaseError,
    MythosError,
    TenantIsolationError,
)
from app.core.result import Failure, Result, Success
from app.core.security_context import SecurityContext
from app.db.models.order import Order, OrderStatus
from app.pathways.write.lifecycle import build_audit_record
from app.pathways.write.mfa import MFAProvider
from app.pathways.write.repository import WriteOrderRepository
from app.pathways.write.schemas import CancelOrderRequest, CancelOrderResponse

logger = logging.getLogger(__name__)

_NIL_UUID: UUID = UUID(int=0)

_CANCELLABLE_STATUSES: frozenset[OrderStatus] = frozenset(
    {OrderStatus.PENDING, OrderStatus.CONFIRMED}
)


def _validate_security_context(ctx: SecurityContext) -> None:
    if ctx.tenant_id == _NIL_UUID:
        raise TenantIsolationError("Security context is missing tenant_id")
    if ctx.current_user_id == _NIL_UUID:
        raise AuthorizationError("Security context is missing current_user_id")


def _validate_cancellable(order: Order) -> None:
    if order.status not in _CANCELLABLE_STATUSES:
        raise BusinessRuleViolation(
            f"Order cannot be cancelled: status is '{order.status}'"
        )
    until: datetime | None = order.cancellable_until
    if until is not None and datetime.now(UTC) >= until:
        raise BusinessRuleViolation("Cancellation window has expired")


async def execute_cancel_order(
    request: CancelOrderRequest,
    ctx: SecurityContext,
    session: AsyncSession,
    mfa_provider: MFAProvider,
) -> Result[CancelOrderResponse]:
    """
    Orchestrates CANCEL_ORDER: validates context → resolves order with 3-key
    lookup → checks ownership and business invariants → runs MFA hook →
    constructs audit record → mutates state inside a transaction → returns a
    safe response. All failures are returned as Failure; no exception escapes.
    """
    try:
        # Step 2 – tenant / user presence guard
        _validate_security_context(ctx)

        repo = WriteOrderRepository(session)

        async with session.begin():
            # Step 3 – resolve target: order_id + tenant_id + user_id
            order = await repo.get_for_cancellation(
                request.order_id,
                tenant_id=ctx.tenant_id,
                user_id=ctx.current_user_id,
            )

            # Steps 3 & 4 – not found or wrong owner → generic safe failure
            if order is None:
                raise AuthorizationError("Order not found or not authorized")

            # Step 4 – defense-in-depth ownership assertion
            if order.user_id != ctx.current_user_id:
                raise AuthorizationError("Order not found or not authorized")

            # Step 5 – business invariant validation
            _validate_cancellable(order)

            # Step 6 – MFA challenge hook
            challenge_token = await mfa_provider.request_challenge(
                ctx.current_user_id, ctx.tenant_id
            )
            mfa_ok = await mfa_provider.verify_challenge(
                ctx.current_user_id, challenge_token
            )
            if not mfa_ok:
                raise AuthorizationError("MFA verification failed")

            # Step 7 – audit record (never includes secrets)
            audit = build_audit_record(
                request_id=ctx.request_id,
                tenant_id=ctx.tenant_id,
                user_id=ctx.current_user_id,
                order_id=request.order_id,
                action="CANCEL_ORDER",
            )
            logger.info(
                "cancel_order audit request_id=%s order_id=%s tenant_id=%s",
                audit.request_id,
                audit.order_id,
                audit.tenant_id,
            )

            # Step 9 – state mutation
            cancelled_at = datetime.now(UTC)
            order.status = OrderStatus.CANCELLED
            order.updated_at = cancelled_at
            await session.flush()

            # Step 10 – safe response; never return internal model
            return Success(
                value=CancelOrderResponse(
                    operation_status="cancelled",
                    order_id=request.order_id,
                    cancelled_at=cancelled_at,
                )
            )

    except MythosError as exc:
        return Failure(error=exc, message=exc.message)
    except Exception:
        return Failure(
            error=DatabaseError("A system error occurred"),
            message="A system error occurred",
        )
