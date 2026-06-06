"""Workflow Automation Engine API routes.

Routes
------
POST /v1/workflows                        create workflow definition
GET  /v1/workflows                        list active workflows (tenant-scoped)
GET  /v1/workflows/{id}                   get workflow definition
DELETE /v1/workflows/{id}                 deactivate workflow
POST /v1/workflows/{id}/execute           trigger execution (synchronous)
GET  /v1/workflows/{id}/executions        list executions for workflow
GET  /v1/workflows/executions/{exec_id}   get execution + step details

Permissions
-----------
workflow.create  — create definitions
workflow.read    — read definitions and executions
workflow.execute — trigger execution
workflow.admin   — deactivate definitions
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_security_context
from app.core.exceptions import (
    ValidationError,
    WorkflowError,
    WorkflowNotFoundError,
)
from app.core.security_context import SecurityContext
from app.db.session import get_session
from app.workflow.schemas import (
    CreateWorkflowRequest,
    ExecutionResponse,
    ExecutionSummaryResponse,
    TriggerExecutionRequest,
    WorkflowResponse,
)
from app.workflow.service import WorkflowService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])

_SecurityCtx = Annotated[SecurityContext, Depends(get_security_context)]
_DbSession = Annotated[AsyncSession, Depends(get_session)]

_PERM_CREATE = "workflow.create"
_PERM_READ = "workflow.read"
_PERM_EXECUTE = "workflow.execute"
_PERM_ADMIN = "workflow.admin"


def _require(ctx: SecurityContext, perm: str) -> None:
    if perm not in ctx.permissions:
        raise HTTPException(status_code=403, detail=f"Permission '{perm}' required")


# ── POST /v1/workflows ────────────────────────────────────────────────────────


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    request: CreateWorkflowRequest,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> WorkflowResponse:
    """Create a new workflow definition.

    Permission: workflow.create
    """
    _require(ctx, _PERM_CREATE)
    svc = WorkflowService(session)
    try:
        return await svc.create_workflow(request, ctx)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── GET /v1/workflows ─────────────────────────────────────────────────────────


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    ctx: _SecurityCtx,
    session: _DbSession,
) -> list[WorkflowResponse]:
    """List active workflow definitions for the authenticated tenant.

    Permission: workflow.read
    """
    _require(ctx, _PERM_READ)
    svc = WorkflowService(session)
    return await svc.list_workflows(ctx)


# ── GET /v1/workflows/{id} ────────────────────────────────────────────────────


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> WorkflowResponse:
    """Get a workflow definition by ID.

    Permission: workflow.read
    """
    _require(ctx, _PERM_READ)
    svc = WorkflowService(session)
    try:
        return await svc.get_workflow(workflow_id, ctx)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


# ── DELETE /v1/workflows/{id} ─────────────────────────────────────────────────


@router.delete("/{workflow_id}", response_model=WorkflowResponse)
async def deactivate_workflow(
    workflow_id: UUID,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> WorkflowResponse:
    """Deactivate a workflow definition (soft delete).

    Permission: workflow.admin
    """
    _require(ctx, _PERM_ADMIN)
    svc = WorkflowService(session)
    try:
        return await svc.deactivate_workflow(workflow_id, ctx)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


# ── POST /v1/workflows/{id}/execute ──────────────────────────────────────────


@router.post("/{workflow_id}/execute", response_model=ExecutionResponse)
async def trigger_execution(
    workflow_id: UUID,
    request: TriggerExecutionRequest,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> ExecutionResponse:
    """Trigger a synchronous workflow execution.

    The request body ``input`` dict is available to all steps as
    ``{{ input.field_name }}``.

    Permission: workflow.execute
    """
    _require(ctx, _PERM_EXECUTE)
    svc = WorkflowService(session)
    try:
        return await svc.trigger_execution(
            workflow_id=workflow_id,
            request_input=request.input,
            ctx=ctx,
            project_id=request.project_id,
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


# ── GET /v1/workflows/{id}/executions ────────────────────────────────────────


@router.get("/{workflow_id}/executions", response_model=list[ExecutionSummaryResponse])
async def list_executions(
    workflow_id: UUID,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> list[ExecutionSummaryResponse]:
    """List past executions for a workflow (most recent first, limit 100).

    Permission: workflow.read
    """
    _require(ctx, _PERM_READ)
    svc = WorkflowService(session)
    try:
        return await svc.list_executions(workflow_id, ctx)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


# ── GET /v1/workflows/executions/{exec_id} ────────────────────────────────────


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: UUID,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> ExecutionResponse:
    """Get a workflow execution with its full step audit trail.

    Permission: workflow.read
    """
    _require(ctx, _PERM_READ)
    svc = WorkflowService(session)
    try:
        return await svc.get_execution(execution_id, ctx)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
