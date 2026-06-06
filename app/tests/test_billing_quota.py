"""Unit tests for QuotaEnforcer."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.billing.models import PLAN_FEATURES, PlanTier
from app.billing.quota import QuotaEnforcer
from app.core.exceptions import QuotaExceededError


def _session_with_plan(plan: str | None = None, request_count: int = 0) -> AsyncMock:
    """Mock AsyncSession that returns a BillingSubscription and usage records.

    Both scalar_one_or_none (subscription) and scalars().all() (usage) are set
    on every result so that repeated session.execute calls work correctly when
    check_feature iterates over multiple features in a loop.
    """
    session = AsyncMock()

    sub = (
        SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            plan=plan,
            status="active",
        )
        if plan is not None
        else None
    )

    usage = SimpleNamespace(request_count=request_count, billing_period="2026-06")

    async def fake_execute(stmt: object) -> MagicMock:
        result = MagicMock()
        result.scalar_one_or_none.return_value = sub
        result.scalars.return_value.all.return_value = (
            [usage] if request_count > 0 else []
        )
        return result

    session.execute = fake_execute
    return session


# ── check_api_request ─────────────────────────────────────────────────────────


class TestCheckApiRequest:
    @pytest.mark.asyncio
    async def test_free_plan_below_limit_passes(self) -> None:
        session = _session_with_plan("free", request_count=500)
        enforcer = QuotaEnforcer(session)
        # Should not raise
        await enforcer.check_api_request(uuid4())

    @pytest.mark.asyncio
    async def test_free_plan_at_limit_raises(self) -> None:
        limit = PLAN_FEATURES[PlanTier.FREE].monthly_api_requests  # 1_000
        session = _session_with_plan("free", request_count=limit)
        enforcer = QuotaEnforcer(session)
        with pytest.raises(QuotaExceededError, match="1,000"):
            await enforcer.check_api_request(uuid4())

    @pytest.mark.asyncio
    async def test_free_plan_over_limit_raises(self) -> None:
        session = _session_with_plan("free", request_count=9999)
        enforcer = QuotaEnforcer(session)
        with pytest.raises(QuotaExceededError):
            await enforcer.check_api_request(uuid4())

    @pytest.mark.asyncio
    async def test_enterprise_plan_unlimited(self) -> None:
        session = _session_with_plan("enterprise", request_count=9_999_999)
        enforcer = QuotaEnforcer(session)
        # Enterprise is unlimited — should never raise
        await enforcer.check_api_request(uuid4())

    @pytest.mark.asyncio
    async def test_no_subscription_defaults_to_free(self) -> None:
        session = _session_with_plan(plan=None, request_count=0)
        enforcer = QuotaEnforcer(session)
        # 0 requests on FREE plan — should pass
        await enforcer.check_api_request(uuid4())

    @pytest.mark.asyncio
    async def test_no_subscription_at_free_limit_raises(self) -> None:
        limit = PLAN_FEATURES[PlanTier.FREE].monthly_api_requests
        session = _session_with_plan(plan=None, request_count=limit)
        enforcer = QuotaEnforcer(session)
        with pytest.raises(QuotaExceededError, match="free"):
            await enforcer.check_api_request(uuid4())

    @pytest.mark.asyncio
    async def test_pro_plan_allows_more_than_free(self) -> None:
        free_limit = PLAN_FEATURES[PlanTier.FREE].monthly_api_requests  # 1_000
        # Use just above free limit — should pass on PRO (50_000 limit)
        session = _session_with_plan("pro", request_count=free_limit + 1)
        enforcer = QuotaEnforcer(session)
        await enforcer.check_api_request(uuid4())


# ── check_feature ─────────────────────────────────────────────────────────────


class TestCheckFeature:
    @pytest.mark.asyncio
    async def test_vision_not_available_on_free_raises(self) -> None:
        session = _session_with_plan("free")
        enforcer = QuotaEnforcer(session)
        with pytest.raises(QuotaExceededError, match="vision"):
            await enforcer.check_feature(uuid4(), "vision")

    @pytest.mark.asyncio
    async def test_workflow_not_available_on_free_raises(self) -> None:
        session = _session_with_plan("free")
        enforcer = QuotaEnforcer(session)
        with pytest.raises(QuotaExceededError, match="workflow"):
            await enforcer.check_feature(uuid4(), "workflow")

    @pytest.mark.asyncio
    async def test_rag_search_available_on_free_passes(self) -> None:
        session = _session_with_plan("free")
        enforcer = QuotaEnforcer(session)
        await enforcer.check_feature(uuid4(), "rag_search")

    @pytest.mark.asyncio
    async def test_vision_available_on_pro_passes(self) -> None:
        session = _session_with_plan("pro")
        enforcer = QuotaEnforcer(session)
        await enforcer.check_feature(uuid4(), "vision")

    @pytest.mark.asyncio
    async def test_all_features_available_on_enterprise(self) -> None:
        session = _session_with_plan("enterprise")
        enforcer = QuotaEnforcer(session)
        for feature in ("vision", "workflow", "rag_search"):
            await enforcer.check_feature(uuid4(), feature)

    @pytest.mark.asyncio
    async def test_unknown_feature_does_not_raise(self) -> None:
        session = _session_with_plan("free")
        enforcer = QuotaEnforcer(session)
        # Unknown features should not block — logged as warning
        await enforcer.check_feature(uuid4(), "unknown_feature")


# ── check_project_limit ───────────────────────────────────────────────────────


class TestCheckProjectLimit:
    @pytest.mark.asyncio
    async def test_free_plan_at_limit_raises(self) -> None:
        limit = PLAN_FEATURES[PlanTier.FREE].max_projects  # 1
        session = _session_with_plan("free")
        enforcer = QuotaEnforcer(session)
        with pytest.raises(QuotaExceededError, match="Project limit"):
            await enforcer.check_project_limit(uuid4(), current_count=limit)

    @pytest.mark.asyncio
    async def test_free_plan_below_limit_passes(self) -> None:
        session = _session_with_plan("free")
        enforcer = QuotaEnforcer(session)
        await enforcer.check_project_limit(uuid4(), current_count=0)

    @pytest.mark.asyncio
    async def test_enterprise_unlimited_always_passes(self) -> None:
        session = _session_with_plan("enterprise")
        enforcer = QuotaEnforcer(session)
        await enforcer.check_project_limit(uuid4(), current_count=999_999)


# ── get_quota_status ──────────────────────────────────────────────────────────


class TestGetQuotaStatus:
    @pytest.mark.asyncio
    async def test_returns_correct_plan_name(self) -> None:
        session = _session_with_plan("pro", request_count=250)
        enforcer = QuotaEnforcer(session)
        status = await enforcer.get_quota_status(uuid4())
        assert status["plan"] == "pro"

    @pytest.mark.asyncio
    async def test_monthly_requests_shows_usage(self) -> None:
        session = _session_with_plan("pro", request_count=250)
        enforcer = QuotaEnforcer(session)
        status = await enforcer.get_quota_status(uuid4())
        assert status["monthly_api_requests"]["used"] == 250
        assert status["monthly_api_requests"]["limit"] == 50_000
        assert status["monthly_api_requests"]["unlimited"] is False

    @pytest.mark.asyncio
    async def test_enterprise_shows_unlimited_flag(self) -> None:
        session = _session_with_plan("enterprise")
        enforcer = QuotaEnforcer(session)
        status = await enforcer.get_quota_status(uuid4())
        assert status["monthly_api_requests"]["unlimited"] is True
        assert status["monthly_api_requests"]["limit"] == -1

    @pytest.mark.asyncio
    async def test_free_plan_feature_flags(self) -> None:
        session = _session_with_plan("free")
        enforcer = QuotaEnforcer(session)
        status = await enforcer.get_quota_status(uuid4())
        assert status["features"]["rag_search"] is True
        assert status["features"]["vision"] is False
        assert status["features"]["workflow"] is False
