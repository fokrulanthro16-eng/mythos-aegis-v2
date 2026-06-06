"""Pydantic API schemas for the workflow engine endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ── Request schemas ───────────────────────────────────────────────────────────


class CreateWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    steps: list[dict[str, Any]] = Field(min_length=1)


class TriggerExecutionRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    project_id: UUID | None = None


# ── Response schemas ──────────────────────────────────────────────────────────


class WorkflowResponse(BaseModel):
    workflow_id: UUID
    name: str
    description: str
    version: int
    is_active: bool
    step_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class StepExecutionResponse(BaseModel):
    step_id: str
    step_name: str
    step_type: str
    step_index: int
    status: str
    attempt_number: int
    max_attempts: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ExecutionResponse(BaseModel):
    execution_id: UUID
    workflow_id: UUID
    workflow_version: int
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    steps: list[StepExecutionResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ExecutionSummaryResponse(BaseModel):
    execution_id: UUID
    workflow_id: UUID
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
