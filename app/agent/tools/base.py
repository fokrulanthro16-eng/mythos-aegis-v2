"""Base classes for agent tools.

Every tool exposes a ToolDefinition (name, description, parameter schema) used
to build the LLM system prompt, and an async execute() method called by the
AgentRuntime.

Security contract:
- execute() must never include secrets, tokens, or raw document content in
  ToolResult.data — tool results are returned to the LLM and persisted in
  agent_messages.
- Tool content logs must never contain the actual data values, only lengths
  and counts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security_context import SecurityContext


@dataclass(frozen=True)
class ToolParameter:
    name: str
    type: str  # "string" | "integer" | "boolean"
    description: str
    required: bool = True
    default: Any = None


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    required_permission: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for inclusion in the LLM system prompt."""
        params: dict[str, Any] = {}
        required: list[str] = []
        for p in self.parameters:
            entry: dict[str, Any] = {
                "type": p.type,
                "description": p.description,
            }
            if p.default is not None:
                entry["default"] = p.default
            params[p.name] = entry
            if p.required:
                required.append(p.name)
        return {
            "name": self.name,
            "description": self.description,
            "parameters": params,
            "required": required,
        }


@dataclass(frozen=True)
class ToolResult:
    success: bool
    data: Any  # JSON-serializable; never contains secrets
    error: str | None = None


class BaseTool(ABC):
    """Abstract base for all agent tools."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition: ...

    @abstractmethod
    async def execute(
        self,
        params: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> ToolResult: ...
