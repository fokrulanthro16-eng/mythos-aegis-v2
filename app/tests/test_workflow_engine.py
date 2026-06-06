"""Unit tests for the workflow execution engine."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import WorkflowStepError
from app.core.security_context import SecurityContext
from app.workflow.engine import WorkflowEngine
from app.workflow.executor import StepExecutor


def _ctx() -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"admin"}),
        permissions=frozenset({"workflow.execute"}),
    )


def _session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    return s


def _make_definition(steps: list[dict[str, Any]]) -> Any:
    return SimpleNamespace(id=uuid4(), steps_json=json.dumps(steps))


def _make_execution(wf_id: UUID | None = None) -> Any:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        workflow_id=wf_id or uuid4(),
        workflow_version=1,
        status="pending",
        input_json="{}",
        output_json="{}",
        triggered_by=uuid4(),
        project_id=None,
        error_message=None,
        started_at=None,
        completed_at=None,
    )


def _transform_step(step_id: str = "s1") -> dict[str, Any]:
    return {
        "id": step_id,
        "name": step_id.title(),
        "type": "transform",
        "config": {"output": {"result": "ok"}},
        "depends_on": [],
        "retry": {"max_attempts": 1, "initial_delay_seconds": 0},
    }


class TestWorkflowEngineSuccess:
    @pytest.mark.asyncio
    async def test_single_step_completes(self) -> None:
        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute = AsyncMock(return_value={"result": "ok"})

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition([_transform_step("s1")])
        ex = _make_execution(defn.id)
        session = _session()

        result = await engine.execute(ex, defn, _ctx(), session)

        assert result.status == "completed"
        mock_executor.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multi_step_executes_all(self) -> None:
        mock_executor = AsyncMock(spec=StepExecutor)
        call_count = 0

        async def fake_execute(
            step: Any,
            context: dict[str, Any],
            ctx: SecurityContext,
            session: Any,
        ) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"step": step.id}

        mock_executor.execute = fake_execute

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition([_transform_step("a"), _transform_step("b")])
        ex = _make_execution(defn.id)

        result = await engine.execute(ex, defn, _ctx(), _session())

        assert result.status == "completed"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_step_output_propagates_to_context(self) -> None:
        captured_contexts: list[dict[str, Any]] = []

        async def fake_execute(
            step: Any,
            context: dict[str, Any],
            ctx: SecurityContext,
            session: Any,
        ) -> dict[str, Any]:
            captured_contexts.append(dict(context))
            return {"value": f"out_{step.id}"}

        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute = fake_execute

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition(
            [
                _transform_step("first"),
                {
                    "id": "second",
                    "name": "Second",
                    "type": "transform",
                    "config": {"output": {}},
                    "depends_on": ["first"],
                    "retry": {"max_attempts": 1, "initial_delay_seconds": 0},
                },
            ]
        )
        ex = _make_execution(defn.id)

        await engine.execute(ex, defn, _ctx(), _session())

        second_ctx = captured_contexts[1]
        assert "first" in second_ctx["steps"]
        assert second_ctx["steps"]["first"]["output"]["value"] == "out_first"

    @pytest.mark.asyncio
    async def test_execution_output_set_to_last_step_output(self) -> None:
        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute = AsyncMock(return_value={"final": "answer"})

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition([_transform_step("last")])
        ex = _make_execution(defn.id)

        result = await engine.execute(ex, defn, _ctx(), _session())

        output = json.loads(result.output_json)
        assert output.get("final") == "answer"

    @pytest.mark.asyncio
    async def test_input_available_in_context(self) -> None:
        captured: list[dict[str, Any]] = []

        async def fake_execute(
            step: Any,
            context: dict[str, Any],
            ctx: SecurityContext,
            session: Any,
        ) -> dict[str, Any]:
            captured.append(context["input"])
            return {}

        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute = fake_execute

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition([_transform_step("s")])
        ex = _make_execution(defn.id)
        ex.input_json = json.dumps({"filename": "invoice.pdf"})

        await engine.execute(ex, defn, _ctx(), _session())

        assert captured[0]["filename"] == "invoice.pdf"


class TestWorkflowEngineFailure:
    @pytest.mark.asyncio
    async def test_step_error_marks_execution_failed(self) -> None:
        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute = AsyncMock(
            side_effect=WorkflowStepError("invalid config")
        )

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition([_transform_step("bad")])
        ex = _make_execution(defn.id)

        result = await engine.execute(ex, defn, _ctx(), _session())

        assert result.status == "failed"
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_failed_execution_has_completed_at(self) -> None:
        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute = AsyncMock(side_effect=WorkflowStepError("boom"))

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition([_transform_step("s")])
        ex = _make_execution(defn.id)

        result = await engine.execute(ex, defn, _ctx(), _session())

        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_subsequent_steps_not_run_after_failure(self) -> None:
        call_ids: list[str] = []

        async def fake_execute(
            step: Any,
            context: dict[str, Any],
            ctx: SecurityContext,
            session: Any,
        ) -> dict[str, Any]:
            call_ids.append(step.id)
            if step.id == "failing_step":
                raise WorkflowStepError("bad step")
            return {}

        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute = fake_execute

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition(
            [_transform_step("failing_step"), _transform_step("second_step")]
        )
        ex = _make_execution(defn.id)

        result = await engine.execute(ex, defn, _ctx(), _session())

        assert result.status == "failed"
        assert "second_step" not in call_ids

    @pytest.mark.asyncio
    async def test_transient_error_retried(self) -> None:
        attempt_count = 0

        async def fake_execute(
            step: Any,
            context: dict[str, Any],
            ctx: SecurityContext,
            session: Any,
        ) -> dict[str, Any]:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise RuntimeError("transient network error")
            return {"ok": True}

        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute = fake_execute

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition(
            [
                {
                    "id": "retried",
                    "name": "Retried",
                    "type": "transform",
                    "config": {"output": {}},
                    "depends_on": [],
                    "retry": {
                        "max_attempts": 3,
                        "initial_delay_seconds": 0,
                        "backoff_multiplier": 1.0,
                        "max_delay_seconds": 0,
                    },
                }
            ]
        )
        ex = _make_execution(defn.id)

        with patch("asyncio.sleep", new=AsyncMock()):
            result = await engine.execute(ex, defn, _ctx(), _session())

        assert result.status == "completed"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_marks_failed(self) -> None:
        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute = AsyncMock(side_effect=RuntimeError("always fails"))

        engine = WorkflowEngine(executor=mock_executor)
        defn = _make_definition(
            [
                {
                    "id": "always_fail",
                    "name": "Always Fail",
                    "type": "transform",
                    "config": {"output": {}},
                    "depends_on": [],
                    "retry": {
                        "max_attempts": 2,
                        "initial_delay_seconds": 0,
                        "backoff_multiplier": 1.0,
                        "max_delay_seconds": 0,
                    },
                }
            ]
        )
        ex = _make_execution(defn.id)

        with patch("asyncio.sleep", new=AsyncMock()):
            result = await engine.execute(ex, defn, _ctx(), _session())

        assert result.status == "failed"
        assert mock_executor.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_unmet_dependency_marks_failed(self) -> None:
        engine = WorkflowEngine()
        defn = _make_definition(
            [
                {
                    "id": "second",
                    "name": "Second",
                    "type": "transform",
                    "config": {"output": {}},
                    "depends_on": ["first"],
                    "retry": {"max_attempts": 1, "initial_delay_seconds": 0},
                }
            ]
        )
        ex = _make_execution(defn.id)

        result = await engine.execute(ex, defn, _ctx(), _session())

        assert result.status == "failed"
        assert "first" in (result.error_message or "")
