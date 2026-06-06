"""Workflow execution engine — orchestrates sequential step execution.

Execution model
---------------
Steps run in definition order.  A step only runs after all steps listed in
its ``depends_on`` set have completed successfully.

Retry policy
------------
Transient failures (any exception *except* ``WorkflowStepError``) are retried
up to ``step.retry.max_attempts`` times with exponential back-off.
``WorkflowStepError`` (logic/config errors) fails immediately without retry.

Audit trail
-----------
Every step creates a ``WorkflowStepExecution`` record.  The overall execution
status is always committed — even on failure — so the audit trail is preserved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import WorkflowExecutionError, WorkflowStepError
from app.core.security_context import SecurityContext
from app.db.models.workflow_definition import WorkflowDefinition
from app.db.models.workflow_execution import WorkflowExecution
from app.db.models.workflow_step_execution import WorkflowStepExecution
from app.observability.metrics import (
    workflow_execution_duration_seconds,
    workflow_executions_total,
    workflow_step_executions_total,
)
from app.workflow.executor import StepExecutor
from app.workflow.models import StepDefinition

logger = logging.getLogger(__name__)

_STATUS_RUNNING = "running"
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"
_STATUS_SKIPPED = "skipped"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_steps(steps_json: str) -> list[StepDefinition]:
    raw: list[dict[str, Any]] = json.loads(steps_json)
    return [StepDefinition.model_validate(s) for s in raw]


class WorkflowEngine:
    """Orchestrate the sequential execution of a workflow."""

    def __init__(self, executor: StepExecutor | None = None) -> None:
        self._executor = executor or StepExecutor()

    async def execute(
        self,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> WorkflowExecution:
        """Run all steps and return the (mutated) execution record.

        Never raises — failures are captured in the execution record.
        """
        steps = _parse_steps(definition.steps_json)
        wall_start = time.monotonic()

        execution.status = _STATUS_RUNNING
        execution.started_at = _now()
        session.add(execution)
        await session.flush()

        context: dict[str, Any] = {
            "input": json.loads(execution.input_json),
            "steps": {},
        }
        completed_ids: set[str] = set()

        try:
            for index, step in enumerate(steps):
                output = await self._run_step(
                    step=step,
                    index=index,
                    context=context,
                    completed_ids=completed_ids,
                    ctx=ctx,
                    session=session,
                    execution_id=execution.id,
                )
                context["steps"][step.id] = {
                    "output": output,
                    "status": _STATUS_COMPLETED,
                }
                completed_ids.add(step.id)

            execution.status = _STATUS_COMPLETED
            execution.output_json = json.dumps(
                context["steps"].get(steps[-1].id, {}).get("output", {})
                if steps
                else {}
            )
            workflow_executions_total.labels(status=_STATUS_COMPLETED).inc()

        except WorkflowExecutionError as exc:
            execution.status = _STATUS_FAILED
            execution.error_message = exc.message
            workflow_executions_total.labels(status=_STATUS_FAILED).inc()
            logger.warning(
                "workflow.execution.failed id=%s reason=%s",
                execution.id,
                exc.message,
            )

        finally:
            execution.completed_at = _now()
            session.add(execution)
            await session.flush()
            elapsed = time.monotonic() - wall_start
            workflow_execution_duration_seconds.observe(elapsed)
            logger.info(
                "workflow.execution.done id=%s status=%s elapsed=%.2fs",
                execution.id,
                execution.status,
                elapsed,
            )

        return execution

    async def _run_step(
        self,
        *,
        step: StepDefinition,
        index: int,
        context: dict[str, Any],
        completed_ids: set[str],
        ctx: SecurityContext,
        session: AsyncSession,
        execution_id: UUID,
    ) -> dict[str, Any]:
        missing = [d for d in step.depends_on if d not in completed_ids]
        if missing:
            raise WorkflowExecutionError(
                f"Step '{step.id}' dependencies not met: {missing}"
            )

        step_rec = WorkflowStepExecution(
            id=uuid4(),
            execution_id=execution_id,
            step_id=step.id,
            step_name=step.name,
            step_type=step.type.value,
            step_index=index,
            status=_STATUS_RUNNING,
            input_json=json.dumps(step.config),
            max_attempts=step.retry.max_attempts,
        )
        step_rec.started_at = _now()
        session.add(step_rec)
        await session.flush()

        output: dict[str, Any] = {}
        last_error: Exception | None = None
        delay = step.retry.initial_delay_seconds

        for attempt in range(1, step.retry.max_attempts + 1):
            step_rec.attempt_number = attempt
            try:
                output = await self._executor.execute(step, context, ctx, session)
                break
            except WorkflowStepError as exc:
                last_error = exc
                step_rec.status = _STATUS_FAILED
                step_rec.error_message = exc.message
                step_rec.completed_at = _now()
                session.add(step_rec)
                await session.flush()
                workflow_step_executions_total.labels(
                    step_type=step.type.value, status=_STATUS_FAILED
                ).inc()
                raise WorkflowExecutionError(
                    f"Step '{step.id}' failed: {exc.message}"
                ) from exc
            except Exception as exc:
                last_error = exc
                if attempt < step.retry.max_attempts:
                    wait = min(delay, step.retry.max_delay_seconds)
                    logger.warning(
                        "workflow.step.retry step=%s attempt=%d/%d wait=%.1fs",
                        step.id,
                        attempt,
                        step.retry.max_attempts,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    delay *= step.retry.backoff_multiplier

        if last_error is not None and not output:
            step_rec.status = _STATUS_FAILED
            step_rec.error_message = str(last_error)
            step_rec.completed_at = _now()
            session.add(step_rec)
            await session.flush()
            workflow_step_executions_total.labels(
                step_type=step.type.value, status=_STATUS_FAILED
            ).inc()
            raise WorkflowExecutionError(
                f"Step '{step.id}' failed after {step.retry.max_attempts} attempts"
            ) from last_error

        step_rec.status = _STATUS_COMPLETED
        step_rec.output_json = json.dumps(output)
        step_rec.completed_at = _now()
        session.add(step_rec)
        await session.flush()
        workflow_step_executions_total.labels(
            step_type=step.type.value, status=_STATUS_COMPLETED
        ).inc()

        logger.info(
            "workflow.step.done step=%s type=%s tenant=%s",
            step.id,
            step.type.value,
            ctx.tenant_id,
        )

        return output
