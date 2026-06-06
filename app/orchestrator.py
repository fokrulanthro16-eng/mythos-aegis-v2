"""Single entry point for all Mythos Aegis execution pathways.

Accepts an IntentParseResult and SecurityContext, routes to the correct
pathway, and synthesizes a safe ResponsePayload.

Global exception boundary guarantees:
- No exception ever escapes this module.
- No traceback, SQL string, or database detail is ever exposed.
- All error paths produce a safe ResponsePayload with a generic warning.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import check_permission
from app.core.exceptions import MythosError
from app.core.result import Failure, Result
from app.core.security_context import SecurityContext
from app.intent.enums import ActionType, Intent
from app.intent.schemas import IntentParseResult
from app.pathways.clarification.service import (
    clarification_request_from_parse_result,
    execute_clarification,
)
from app.pathways.rag_vision.interfaces import (
    DamageVisionProvider,
    PolicySearchProvider,
    ReceiptOCRProvider,
)
from app.pathways.rag_vision.schemas import (
    DamageAnalysisRequest,
    PolicySearchRequest,
    ReceiptValidationRequest,
)
from app.pathways.rag_vision.service import (
    analyze_damage,
    search_policies,
    validate_receipt,
)
from app.pathways.sql_airlock.schemas import AnalyticsRequest
from app.pathways.sql_airlock.service import execute_analytics_query
from app.pathways.write.mfa import MFAProvider
from app.pathways.write.schemas import CancelOrderRequest
from app.pathways.write.service import execute_cancel_order
from app.response.schemas import ResponsePayload
from app.response.synthesizer import synthesize

logger = logging.getLogger(__name__)

_NIL_UUID: UUID = UUID(int=0)

# Type alias for any unparameterised result used internally.
_AnyResult = Result[Any]


# ---------------------------------------------------------------------------
# Entity extraction helpers
# ---------------------------------------------------------------------------


def _uuid_from(entities: dict[str, Any], key: str) -> UUID:
    raw = entities.get(key, "")
    try:
        return UUID(str(raw))
    except (ValueError, AttributeError):
        return _NIL_UUID


def _str_from(entities: dict[str, Any], key: str) -> str:
    return str(entities.get(key, ""))


# ---------------------------------------------------------------------------
# Per-action-type routers — each returns Result[Any]; never raises
# ---------------------------------------------------------------------------


async def _route_write(
    parse_result: IntentParseResult,
    ctx: SecurityContext,
    session: AsyncSession | None,
    mfa_provider: MFAProvider | None,
) -> _AnyResult:
    if session is None:
        return Failure(
            error=MythosError("No database session provided"),
            message="Database session required for write operations",
        )
    if mfa_provider is None:
        return Failure(
            error=MythosError("No MFA provider configured"),
            message="MFA provider required for write operations",
        )
    order_id = _uuid_from(parse_result.entities, "order_id")
    request = CancelOrderRequest(order_id=order_id)
    result: _AnyResult = await execute_cancel_order(request, ctx, session, mfa_provider)
    return result


async def _route_sql(
    parse_result: IntentParseResult,
    ctx: SecurityContext,
    session: AsyncSession | None,
) -> _AnyResult:
    if session is None:
        return Failure(
            error=MythosError("No database session provided"),
            message="Database session required for analytics",
        )
    sql = _str_from(parse_result.entities, "sql")
    request = AnalyticsRequest(sql=sql, user_id=ctx.current_user_id)
    result: _AnyResult = await execute_analytics_query(request, session)
    return result


async def _route_rag(
    parse_result: IntentParseResult,
    ctx: SecurityContext,
    policy_provider: PolicySearchProvider | None,
    receipt_provider: ReceiptOCRProvider | None,
    damage_provider: DamageVisionProvider | None,
) -> _AnyResult:
    intent = parse_result.intent

    if intent == Intent.POLICY_SEARCH:
        if policy_provider is None:
            return Failure(
                error=MythosError("No policy provider configured"),
                message="Policy search provider required",
            )
        req = PolicySearchRequest(
            query=_str_from(parse_result.entities, "query"),
            tenant_id=ctx.tenant_id,
            user_id=ctx.current_user_id,
        )
        result: _AnyResult = await search_policies(req, policy_provider)
        return result

    if intent == Intent.VISION_RECEIPT_VALIDATE:
        if receipt_provider is None:
            return Failure(
                error=MythosError("No OCR provider configured"),
                message="Receipt OCR provider required",
            )
        req_r = ReceiptValidationRequest(
            image_url=_str_from(parse_result.entities, "image_url"),
            tenant_id=ctx.tenant_id,
            user_id=ctx.current_user_id,
        )
        result = await validate_receipt(req_r, receipt_provider)
        return result

    if intent == Intent.VISION_DAMAGE_ANALYSIS:
        if damage_provider is None:
            return Failure(
                error=MythosError("No vision provider configured"),
                message="Damage vision provider required",
            )
        req_d = DamageAnalysisRequest(
            image_url=_str_from(parse_result.entities, "image_url"),
            tenant_id=ctx.tenant_id,
            user_id=ctx.current_user_id,
        )
        result = await analyze_damage(req_d, damage_provider)
        return result

    return Failure(
        error=MythosError(f"Unsupported RAG intent: {parse_result.intent}"),
        message="No handler registered for this intent",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def route(
    parse_result: IntentParseResult,
    ctx: SecurityContext,
    *,
    session: AsyncSession | None = None,
    mfa_provider: MFAProvider | None = None,
    policy_provider: PolicySearchProvider | None = None,
    receipt_provider: ReceiptOCRProvider | None = None,
    damage_provider: DamageVisionProvider | None = None,
) -> ResponsePayload:
    """Route an intent to the correct pathway and return a safe ResponsePayload.

    This function never raises; all failures produce a safe payload.
    """
    request_id = str(ctx.request_id)
    try:
        # RBAC check — before any pathway dispatching.
        permission_failure = check_permission(ctx, parse_result)
        if permission_failure is not None:
            return synthesize(permission_failure, request_id=request_id)

        pathway_result: _AnyResult

        if parse_result.action_type == ActionType.WRITE_MUTATION:
            pathway_result = await _route_write(
                parse_result, ctx, session, mfa_provider
            )
        elif parse_result.action_type == ActionType.SQL_ANALYTICS:
            pathway_result = await _route_sql(parse_result, ctx, session)
        elif parse_result.action_type == ActionType.RAG_VISION:
            pathway_result = await _route_rag(
                parse_result,
                ctx,
                policy_provider=policy_provider,
                receipt_provider=receipt_provider,
                damage_provider=damage_provider,
            )
        elif parse_result.action_type == ActionType.CLARIFICATION:
            clarification_req = clarification_request_from_parse_result(parse_result)
            clarification_result: _AnyResult = await execute_clarification(
                clarification_req
            )
            pathway_result = clarification_result
        else:
            # NOOP or any future unregistered action type
            pathway_result = Failure(
                error=MythosError("No action available for this intent"),
                message="No action is available for this request",
            )

        return synthesize(pathway_result, request_id=request_id)

    except MythosError:
        logger.warning("MythosError escaped route boundary", exc_info=True)
        return ResponsePayload(
            summary="A system error occurred. Please try again.",
            warnings=["Request could not be completed. Please try again."],
            request_id=request_id,
        )
    except TimeoutError:
        logger.warning("TimeoutError in route boundary")
        return ResponsePayload(
            summary="Request timed out. Please try again.",
            warnings=["Request timed out."],
            request_id=request_id,
        )
    except Exception:
        logger.exception("Unexpected exception in route boundary")
        return ResponsePayload(
            summary="An unexpected error occurred. Please try again.",
            warnings=["An unexpected error occurred."],
            request_id=request_id,
        )
