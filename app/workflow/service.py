"""WorkflowService — CRUD for workflow definitions and execution triggering.

Security invariants
-------------------
- tenant_id is always sourced from the validated SecurityContext.
- No workflow definition or execution crosses tenant boundaries.
- Workflow input data is stored as JSON; no secrets are logged.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import WorkflowError, WorkflowNotFoundError
from app.core.security_context import SecurityContext
from app.db.models.workflow_definition import WorkflowDefinition
from app.db.models.workflow_execution import WorkflowExecution
from app.db.models.workflow_step_execution import WorkflowStepExecution
from app.workflow.engine import WorkflowEngine
from app.workflow.models import WorkflowDefinitionModel
from app.workflow.schemas import (
    CreateWorkflowRequest,
    ExecutionResponse,
    ExecutionSummaryResponse,
    StepExecutionResponse,
    WorkflowResponse,
)

logger = logging.getLogger(__name__)

_STATUS_PENDING = "pending"


class WorkflowService:
    """CRUD + execution orchestration for workflows."""

    def __init__(
        self,
        session: AsyncSession,
        engine: WorkflowEngine | None = None,
    ) -> None:
        self._session = session
        self._engine = engine or WorkflowEngine()

    # ── Definitions ───────────────────────────────────────────────────────────

    async def create_workflow(
        self,
        request: CreateWorkflowRequest,
        ctx: SecurityContext,
    ) -> WorkflowResponse:
        definition_model = WorkflowDefinitionModel(
            name=request.name,
            description=request.description,
            steps=request.steps,
        )

        definition = WorkflowDefinition(
            id=uuid4(),
            tenant_id=ctx.tenant_id,
            name=definition_model.name,
            description=definition_model.description,
            steps_json=json.dumps([s.model_dump() for s in definition_model.steps]),
            version=1,
            is_active=True,
            created_by=ctx.current_user_id,
        )
        self._session.add(definition)
        await self._session.flush()

        logger.info(
            "workflow.definition.created id=%s name=%s tenant=%s",
            definition.id,
            definition.name,
            ctx.tenant_id,
        )

        return self._to_workflow_response(definition)

    async def list_workflows(
        self,
        ctx: SecurityContext,
        *,
        include_inactive: bool = False,
    ) -> list[WorkflowResponse]:
        stmt = select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == ctx.tenant_id
        )
        if not include_inactive:
            stmt = stmt.where(WorkflowDefinition.is_active.is_(True))
        stmt = stmt.order_by(WorkflowDefinition.created_at.desc())
        result = await self._session.execute(stmt)
        definitions = result.scalars().all()
        return [self._to_workflow_response(d) for d in definitions]

    async def get_workflow(
        self,
        workflow_id: UUID,
        ctx: SecurityContext,
    ) -> WorkflowResponse:
        definition = await self._fetch_definition(workflow_id, ctx)
        return self._to_workflow_response(definition)

    async def deactivate_workflow(
        self,
        workflow_id: UUID,
        ctx: SecurityContext,
    ) -> WorkflowResponse:
        definition = await self._fetch_definition(workflow_id, ctx)
        definition.is_active = False
        self._session.add(definition)
        await self._session.flush()
        return self._to_workflow_response(definition)

    # ── Execution ─────────────────────────────────────────────────────────────

    async def trigger_execution(
        self,
        workflow_id: UUID,
        request_input: dict[str, Any],
        ctx: SecurityContext,
        *,
        project_id: UUID | None = None,
    ) -> ExecutionResponse:
        definition = await self._fetch_definition(workflow_id, ctx)

        if not definition.is_active:
            raise WorkflowError(f"Workflow '{definition.name}' is not active")

        execution = WorkflowExecution(
            id=uuid4(),
            tenant_id=ctx.tenant_id,
            workflow_id=workflow_id,
            workflow_version=definition.version,
            status=_STATUS_PENDING,
            input_json=json.dumps(request_input),
            triggered_by=ctx.current_user_id,
            project_id=project_id,
        )
        self._session.add(execution)
        await self._session.flush()

        execution = await self._engine.execute(
            execution=execution,
            definition=definition,
            ctx=ctx,
            session=self._session,
        )

        steps = await self._fetch_steps(execution.id)
        return self._to_execution_response(execution, steps)

    async def get_execution(
        self,
        execution_id: UUID,
        ctx: SecurityContext,
    ) -> ExecutionResponse:
        result = await self._session.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.tenant_id == ctx.tenant_id,
            )
        )
        execution = result.scalar_one_or_none()
        if execution is None:
            raise WorkflowNotFoundError(f"Execution '{execution_id}' not found")
        steps = await self._fetch_steps(execution_id)
        return self._to_execution_response(execution, steps)

    async def list_executions(
        self,
        workflow_id: UUID,
        ctx: SecurityContext,
    ) -> list[ExecutionSummaryResponse]:
        await self._fetch_definition(workflow_id, ctx)
        result = await self._session.execute(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.tenant_id == ctx.tenant_id,
            )
            .order_by(WorkflowExecution.created_at.desc())
            .limit(100)
        )
        executions = result.scalars().all()
        return [self._to_execution_summary(e) for e in executions]

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _fetch_definition(
        self, workflow_id: UUID, ctx: SecurityContext
    ) -> WorkflowDefinition:
        result = await self._session.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.tenant_id == ctx.tenant_id,
            )
        )
        definition = result.scalar_one_or_none()
        if definition is None:
            raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")
        return definition

    async def _fetch_steps(self, execution_id: UUID) -> list[WorkflowStepExecution]:
        result = await self._session.execute(
            select(WorkflowStepExecution)
            .where(WorkflowStepExecution.execution_id == execution_id)
            .order_by(WorkflowStepExecution.step_index)
        )
        return list(result.scalars().all())

    @staticmethod
    def _to_workflow_response(d: WorkflowDefinition) -> WorkflowResponse:
        try:
            steps_list = json.loads(d.steps_json)
            step_count = len(steps_list)
        except Exception:
            step_count = 0
        return WorkflowResponse(
            workflow_id=d.id,
            name=d.name,
            description=d.description,
            version=d.version,
            is_active=d.is_active,
            step_count=step_count,
            created_at=d.created_at,
        )

    @staticmethod
    def _to_execution_response(
        e: WorkflowExecution,
        steps: list[WorkflowStepExecution],
    ) -> ExecutionResponse:
        return ExecutionResponse(
            execution_id=e.id,
            workflow_id=e.workflow_id,
            workflow_version=e.workflow_version,
            status=e.status,
            error_message=e.error_message,
            started_at=e.started_at,
            completed_at=e.completed_at,
            created_at=e.created_at,
            steps=[
                StepExecutionResponse(
                    step_id=s.step_id,
                    step_name=s.step_name,
                    step_type=s.step_type,
                    step_index=s.step_index,
                    status=s.status,
                    attempt_number=s.attempt_number,
                    max_attempts=s.max_attempts,
                    error_message=s.error_message,
                    started_at=s.started_at,
                    completed_at=s.completed_at,
                )
                for s in steps
            ],
        )

    @staticmethod
    def _to_execution_summary(e: WorkflowExecution) -> ExecutionSummaryResponse:
        return ExecutionSummaryResponse(
            execution_id=e.id,
            workflow_id=e.workflow_id,
            status=e.status,
            started_at=e.started_at,
            completed_at=e.completed_at,
            created_at=e.created_at,
        )
