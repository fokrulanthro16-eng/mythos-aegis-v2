"""AI Gateway service layer.

Orchestrates the full AI generation pipeline:
  1. Validate tenant isolation (request.tenant_id == ctx.tenant_id).
  2. Check JWT permission ``ai.generate``.
  3. Check monthly quota via QuotaService.
  4. Select provider via AIGatewayRouter.
  5. Generate completion.
  6. Estimate cost via cost_engine.
  7. Record Prometheus metrics.
  8. Persist usage increment (non-fatal on failure).
  9. Return Success[AIGatewayResponse] or a typed Failure.

Security invariants
-------------------
- Prompt content is NEVER written to any log.
- Secrets (JWT, API keys) are NEVER logged.
- ``tenant_id`` is always sourced from the validated SecurityContext.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_gateway.cost_engine import calculate_cost
from app.ai_gateway.providers.base import BaseAIProvider
from app.ai_gateway.providers.ollama_provider import OllamaProvider
from app.ai_gateway.quota import QuotaService
from app.ai_gateway.router import AIGatewayRouter
from app.ai_gateway.schemas import AIGatewayRequest, AIGatewayResponse
from app.core.exceptions import (
    AIProviderUnavailableError,
    AuthorizationError,
)
from app.core.result import Failure, Result, Success
from app.core.security_context import SecurityContext
from app.observability.metrics import (
    ai_cost_total,
    ai_failures_total,
    ai_requests_total,
    ai_tokens_total,
)
from app.saas.repository import UsageRepository

logger = logging.getLogger(__name__)

_AI_PERMISSION = "ai.generate"


def _billing_period(dt: datetime | None = None) -> str:
    """Return ``'YYYY-MM'`` for *dt* (defaults to UTC now)."""
    return (dt or datetime.now(UTC)).strftime("%Y-%m")


class AIGatewayService:
    """Orchestrate AI generation with quota, routing, metering, and metrics."""

    def __init__(
        self,
        session: AsyncSession,
        router: AIGatewayRouter | None = None,
    ) -> None:
        self._session = session
        self._router = router or AIGatewayRouter(OllamaProvider())
        self._quota = QuotaService(session)
        self._usage = UsageRepository(session)

    async def generate(
        self,
        request: AIGatewayRequest,
        ctx: SecurityContext,
    ) -> Result[AIGatewayResponse]:
        """Run the full pipeline and return a typed Result.

        Never raises — all failures are returned as ``Failure`` values.
        Prompt content is never passed to any logger.
        """
        # 1. Tenant isolation — always use ctx.tenant_id, never request.tenant_id.
        tenant_id: UUID = ctx.tenant_id

        # 2. Permission gate.
        if _AI_PERMISSION not in ctx.permissions:
            ai_failures_total.labels(
                provider="gateway", failure_type="permission_denied"
            ).inc()
            return Failure(
                error=AuthorizationError("permission_denied"),
                message=f"Permission '{_AI_PERMISSION}' is required.",
            )

        billing_period = _billing_period()

        # 3. Quota check.
        quota_result = await self._quota.check(
            tenant_id,
            billing_period,
            project_id=request.project_id,
        )
        if isinstance(quota_result, Failure):
            ai_failures_total.labels(
                provider="gateway", failure_type="quota_exceeded"
            ).inc()
            return quota_result

        # 4. Select provider.
        provider: BaseAIProvider = self._router.select_provider(request.task_type)

        # 5. Generate — prompt_chars logged, prompt content never logged.
        logger.info(
            "ai_gateway.generate provider=%s task=%s prompt_chars=%d tokens=%d",
            provider.provider_name,
            request.task_type,
            len(request.prompt),
            request.max_tokens,
        )
        ai_requests_total.labels(
            provider=provider.provider_name,
            task_type=request.task_type,
        ).inc()

        try:
            gen = await provider.generate(
                request.prompt,
                max_tokens=request.max_tokens,
            )
        except AIProviderUnavailableError as exc:
            ai_failures_total.labels(
                provider=provider.provider_name,
                failure_type="provider_unavailable",
            ).inc()
            logger.warning(
                "ai_gateway.unavailable provider=%s: %s",
                provider.provider_name,
                exc.message,
            )
            return Failure(error=exc, message=exc.message)
        except Exception as exc:  # noqa: BLE001
            ai_failures_total.labels(
                provider=provider.provider_name,
                failure_type="unknown",
            ).inc()
            logger.exception(
                "ai_gateway.unexpected_error provider=%s", provider.provider_name
            )
            return Failure(error=exc, message="AI generation failed unexpectedly.")

        # 6. Cost.
        cost = calculate_cost(
            gen.provider,
            gen.input_tokens_estimate,
            gen.output_tokens_estimate,
        )

        # 7. Metrics.
        ai_tokens_total.labels(provider=gen.provider, token_type="input").inc(
            gen.input_tokens_estimate
        )
        ai_tokens_total.labels(provider=gen.provider, token_type="output").inc(
            gen.output_tokens_estimate
        )
        ai_cost_total.labels(provider=gen.provider).inc(cost)

        # 8. Persist usage (non-fatal).
        try:
            await self._usage.increment(
                tenant_id=tenant_id,
                billing_period=billing_period,
                project_id=request.project_id,
                ai_call_count=1,
                token_usage=gen.input_tokens_estimate + gen.output_tokens_estimate,
            )
        except Exception:  # noqa: BLE001
            logger.exception("ai_gateway.usage_persist_failed tenant_id=%s", tenant_id)

        # 9. Return.
        return Success(
            AIGatewayResponse(
                provider=gen.provider,
                model=gen.model,
                output=gen.output,
                input_tokens_estimate=gen.input_tokens_estimate,
                output_tokens_estimate=gen.output_tokens_estimate,
                estimated_cost=cost,
                safety_warnings=[],
            )
        )
