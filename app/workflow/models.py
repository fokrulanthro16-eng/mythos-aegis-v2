"""Pydantic domain models for workflow definitions and step configs.

These are the in-memory representations parsed from and serialised to the
``steps_json`` column in ``WorkflowDefinition``.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class StepType(StrEnum):
    AGENT_TASK = "agent_task"
    RAG_SEARCH = "rag_search"
    RAG_INDEX = "rag_index"
    VISION_ANALYZE = "vision_analyze"
    VISION_EXTRACT = "vision_extract"
    TRANSFORM = "transform"


_SLUG_RE = re.compile(r"^[a-z0-9_-]+$")


class RetryConfig(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_delay_seconds: float = Field(default=1.0, ge=0.0, le=60.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    max_delay_seconds: float = Field(default=60.0, ge=0.0, le=300.0)


class StepDefinition(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    type: StepType
    config: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    @field_validator("id")
    @classmethod
    def id_must_be_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "step id must contain only lowercase letters, digits, "
                "underscores, or hyphens"
            )
        return v


class WorkflowDefinitionModel(BaseModel):
    """Full workflow blueprint — name, description, and ordered steps."""

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    steps: list[StepDefinition] = Field(min_length=1)

    @field_validator("steps")
    @classmethod
    def validate_unique_step_ids(
        cls, steps: list[StepDefinition]
    ) -> list[StepDefinition]:
        ids = [s.id for s in steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Step IDs must be unique within a workflow")
        return steps

    @model_validator(mode="after")
    def validate_dependencies_exist(self) -> WorkflowDefinitionModel:
        ids = {s.id for s in self.steps}
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in ids:
                    raise ValueError(
                        f"Step '{step.id}' depends on unknown step '{dep}'"
                    )
        return self
