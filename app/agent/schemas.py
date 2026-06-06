"""Pydantic schemas for the agent API layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ── Tool wire types ───────────────────────────────────────────────────────────


class ToolParameterSchema(BaseModel):
    type: str
    description: str
    default: Any = None


class ToolDefinitionSchema(BaseModel):
    name: str
    description: str
    parameters: dict[str, ToolParameterSchema]
    required: list[str]
    required_permission: str | None = None


class ToolCallRecord(BaseModel):
    tool_name: str
    params: dict[str, Any]
    success: bool
    error: str | None = None


# ── Session ───────────────────────────────────────────────────────────────────


class CreateSessionRequest(BaseModel):
    project_id: UUID
    title: str = Field(default="New conversation", max_length=500)


class SessionResponse(BaseModel):
    session_id: UUID
    project_id: UUID
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Message history ───────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    message_id: UUID
    role: str
    content: str
    tool_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionHistoryResponse(BaseModel):
    session_id: UUID
    title: str
    messages: list[MessageResponse]


# ── Single-turn run ───────────────────────────────────────────────────────────


class AgentRunRequest(BaseModel):
    project_id: UUID
    question: str = Field(min_length=1, max_length=4096)
    max_iterations: int = Field(default=5, ge=1, le=10)


class AgentRunResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    iterations: int
    session_id: UUID | None = None


# ── Multi-turn chat ───────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4096)
    max_iterations: int = Field(default=5, ge=1, le=10)


class ChatResponse(BaseModel):
    answer: str
    session_id: UUID
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    iterations: int
