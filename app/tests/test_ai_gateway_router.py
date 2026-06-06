"""Tests for the AI Gateway router and service layer.

The session and AI provider are mocked throughout — no DB or Ollama needed.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai_gateway.cost_engine import calculate_cost, estimate_tokens
from app.ai_gateway.providers.base import BaseAIProvider, GenerateResult
from app.ai_gateway.providers.ollama_provider import OllamaProvider
from app.ai_gateway.router import AIGatewayRouter
from app.ai_gateway.schemas import AIGatewayRequest, AIGatewayResponse
from app.ai_gateway.service import AIGatewayService, _billing_period
from app.core.exceptions import AIProviderUnavailableError
from app.core.result import Failure, Success
from app.core.security_context import SecurityContext

# ── Shared fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    return session


@pytest.fixture
def ctx() -> SecurityContext:
    """SecurityContext with ai.generate permission."""
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=frozenset({"ai.generate"}),
    )


@pytest.fixture
def ctx_no_permission() -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=frozenset(),
    )


@pytest.fixture
def good_generate_result() -> GenerateResult:
    return GenerateResult(
        output="The answer is 42.",
        input_tokens_estimate=10,
        output_tokens_estimate=5,
        model="llama3.1",
        provider="ollama",
    )


@pytest.fixture
def mock_provider(good_generate_result: GenerateResult) -> MagicMock:
    provider = MagicMock(spec=BaseAIProvider)
    provider.provider_name = "ollama"
    provider.default_model = "llama3.1"
    provider.generate = AsyncMock(return_value=good_generate_result)
    provider.estimate_cost = MagicMock(return_value=0.0)
    return provider


@pytest.fixture
def ai_request(ctx: SecurityContext) -> AIGatewayRequest:
    return AIGatewayRequest(
        tenant_id=ctx.tenant_id,
        task_type="generate",
        prompt="What is the meaning of life?",
        max_tokens=100,
    )


# ── Router tests ──────────────────────────────────────────────────────────────


def test_router_default_provider_is_ollama() -> None:
    router = AIGatewayRouter()
    provider = router.select_provider("generate")
    assert isinstance(provider, OllamaProvider)


def test_router_uses_injected_provider(mock_provider: MagicMock) -> None:
    router = AIGatewayRouter(ollama=mock_provider)
    assert router.select_provider("generate") is mock_provider


def test_router_routes_all_task_types_to_ollama(mock_provider: MagicMock) -> None:
    router = AIGatewayRouter(ollama=mock_provider)
    for task in ("generate", "summarize", "classify", "embedding", "unknown"):
        assert router.select_provider(task) is mock_provider


def test_router_available_providers_contains_ollama() -> None:
    router = AIGatewayRouter()
    assert "ollama" in router.available_providers


def test_router_available_providers_returns_injected(
    mock_provider: MagicMock,
) -> None:
    router = AIGatewayRouter(ollama=mock_provider)
    assert router.available_providers["ollama"] is mock_provider


# ── Cost engine tests ─────────────────────────────────────────────────────────


def test_estimate_tokens_minimum_one() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("a") == 1


def test_estimate_tokens_four_chars_per_token() -> None:
    assert estimate_tokens("x" * 400) == 100


def test_calculate_cost_ollama_is_zero() -> None:
    assert calculate_cost("ollama", 1_000_000, 1_000_000) == 0.0


def test_calculate_cost_unknown_provider_is_zero() -> None:
    assert calculate_cost("unknown-provider", 5_000, 5_000) == 0.0


def test_calculate_cost_case_insensitive() -> None:
    assert calculate_cost("OLLAMA", 100, 100) == 0.0


# ── _billing_period helper ────────────────────────────────────────────────────


def test_billing_period_format() -> None:
    bp = _billing_period()
    assert len(bp) == 7
    assert bp[4] == "-"


def test_billing_period_specific_date() -> None:
    from datetime import UTC, datetime

    dt = datetime(2026, 3, 15, tzinfo=UTC)
    assert _billing_period(dt) == "2026-03"


# ── Service: permission gate ──────────────────────────────────────────────────


async def test_service_rejects_missing_permission(
    mock_session: AsyncMock,
    ctx_no_permission: SecurityContext,
    ai_request: AIGatewayRequest,
) -> None:
    ai_request = ai_request.model_copy(
        update={"tenant_id": ctx_no_permission.tenant_id}
    )
    svc = AIGatewayService(mock_session)
    result = await svc.generate(ai_request, ctx_no_permission)
    assert isinstance(result, Failure)
    assert "ai.generate" in result.message


async def test_service_accepts_correct_permission(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    ai_request: AIGatewayRequest,
    mock_provider: MagicMock,
) -> None:
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    result = await svc.generate(ai_request, ctx)
    assert isinstance(result, Success)


# ── Service: routing works ────────────────────────────────────────────────────


async def test_service_calls_provider_generate(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    ai_request: AIGatewayRequest,
    mock_provider: MagicMock,
) -> None:
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    await svc.generate(ai_request, ctx)
    mock_provider.generate.assert_called_once()


async def test_service_response_contains_output(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    ai_request: AIGatewayRequest,
    mock_provider: MagicMock,
) -> None:
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    result = await svc.generate(ai_request, ctx)
    assert isinstance(result, Success)
    assert result.value.output == "The answer is 42."


async def test_service_response_contains_provider_and_model(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    ai_request: AIGatewayRequest,
    mock_provider: MagicMock,
) -> None:
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    result = await svc.generate(ai_request, ctx)
    assert isinstance(result, Success)
    assert result.value.provider == "ollama"
    assert result.value.model == "llama3.1"


async def test_service_cost_is_zero_for_ollama(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    ai_request: AIGatewayRequest,
    mock_provider: MagicMock,
) -> None:
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    result = await svc.generate(ai_request, ctx)
    assert isinstance(result, Success)
    assert result.value.estimated_cost == 0.0


# ── Service: usage record created ────────────────────────────────────────────


async def test_service_increments_usage(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    ai_request: AIGatewayRequest,
    mock_provider: MagicMock,
) -> None:
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    await svc.generate(ai_request, ctx)
    # The usage repository calls session.flush() — verify session interaction.
    assert mock_session.flush.called or mock_session.execute.called


async def test_service_usage_failure_is_non_fatal(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    ai_request: AIGatewayRequest,
    mock_provider: MagicMock,
) -> None:
    """A crash in usage persistence must not fail the AI response."""
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    # Patch only UsageRepository.increment to raise — quota check is unaffected.
    svc._usage.increment = AsyncMock(side_effect=RuntimeError("DB down"))  # type: ignore[method-assign]
    result = await svc.generate(ai_request, ctx)
    # Even though usage persistence failed, the generation succeeded.
    assert isinstance(result, Success)
    assert result.value.output == "The answer is 42."


# ── Service: safe failure when Ollama unavailable ─────────────────────────────


async def test_service_returns_failure_when_provider_unavailable(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    ai_request: AIGatewayRequest,
    mock_provider: MagicMock,
) -> None:
    mock_provider.generate = AsyncMock(
        side_effect=AIProviderUnavailableError("Ollama not reachable")
    )
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    result = await svc.generate(ai_request, ctx)
    assert isinstance(result, Failure)
    assert isinstance(result.error, AIProviderUnavailableError)
    assert "not reachable" in result.message


async def test_service_returns_failure_on_unexpected_error(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    ai_request: AIGatewayRequest,
    mock_provider: MagicMock,
) -> None:
    mock_provider.generate = AsyncMock(side_effect=RuntimeError("boom"))
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    result = await svc.generate(ai_request, ctx)
    assert isinstance(result, Failure)


# ── Service: prompt not logged ────────────────────────────────────────────────


async def test_service_does_not_log_prompt(
    mock_session: AsyncMock,
    ctx: SecurityContext,
    mock_provider: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive = "DO_NOT_LOG_THIS_PROMPT_CONTENT_XYZ"
    req = AIGatewayRequest(
        tenant_id=ctx.tenant_id,
        task_type="generate",
        prompt=sensitive,
        max_tokens=50,
    )
    router = AIGatewayRouter(ollama=mock_provider)
    svc = AIGatewayService(mock_session, router=router)
    with caplog.at_level(logging.DEBUG, logger="app.ai_gateway"):
        await svc.generate(req, ctx)
    for record in caplog.records:
        assert sensitive not in record.getMessage()


# ── Service: no API key required ─────────────────────────────────────────────


def test_ollama_provider_requires_no_api_key() -> None:
    """OllamaProvider must have no API key fields."""
    provider = OllamaProvider()
    for attr in ("api_key", "_api_key", "token", "_token", "secret", "_secret"):
        assert not hasattr(provider, attr), f"Unexpected attribute: {attr}"


# ── Service: response schema structure ───────────────────────────────────────


def test_ai_gateway_response_has_safety_warnings_field() -> None:
    resp = AIGatewayResponse(
        provider="ollama",
        model="llama3.1",
        output="hi",
        input_tokens_estimate=1,
        output_tokens_estimate=1,
        estimated_cost=0.0,
    )
    assert resp.safety_warnings == []


def test_ai_gateway_response_accepts_warnings() -> None:
    resp = AIGatewayResponse(
        provider="ollama",
        model="llama3.1",
        output="hi",
        input_tokens_estimate=1,
        output_tokens_estimate=1,
        estimated_cost=0.0,
        safety_warnings=["content_policy_warning"],
    )
    assert "content_policy_warning" in resp.safety_warnings
