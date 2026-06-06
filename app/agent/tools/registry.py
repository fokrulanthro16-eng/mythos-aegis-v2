"""Tool registry — central catalogue of all available agent tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.tools.base import BaseTool, ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        return [t.definition for t in self._tools.values()]

    def all_names(self) -> list[str]:
        return list(self._tools.keys())

    @classmethod
    def default(cls) -> ToolRegistry:
        """Build the registry with all built-in tools."""
        from app.agent.tools.audit_log import AuditLogTool
        from app.agent.tools.rag_search import RAGSearchTool
        from app.agent.tools.rbac_policy import RBACPolicyTool
        from app.agent.tools.sql_airlock import SQLAirlockTool
        from app.agent.tools.tenant_lookup import TenantLookupTool

        registry = cls()
        registry.register(RAGSearchTool())
        registry.register(TenantLookupTool())
        registry.register(SQLAirlockTool())
        from app.agent.tools.vision_analyze import VisionAnalyzeTool

        registry.register(RBACPolicyTool())
        registry.register(AuditLogTool())
        registry.register(VisionAnalyzeTool())
        return registry


_default_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Return the process-wide default registry (lazy-initialized singleton)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry.default()
    return _default_registry
