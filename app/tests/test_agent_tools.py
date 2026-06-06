"""Unit tests for all five agent tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agent.tools.audit_log import AuditLogTool
from app.agent.tools.rag_search import RAGSearchTool
from app.agent.tools.rbac_policy import RBACPolicyTool
from app.agent.tools.sql_airlock import SQLAirlockTool, _validate_select_only
from app.agent.tools.tenant_lookup import TenantLookupTool
from app.core.exceptions import SqlAirlockViolation
from app.core.security_context import SecurityContext


def _ctx(permissions: frozenset[str] | None = None) -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=(
            permissions
            if permissions is not None
            else frozenset({"rag.search", "analytics.read", "agent.run"})
        ),
    )


def _session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    return s


# ── RAGSearchTool ─────────────────────────────────────────────────────────────


class TestRAGSearchTool:
    def test_definition_name(self) -> None:
        assert RAGSearchTool().definition.name == "rag_search"

    def test_definition_has_required_permission(self) -> None:
        assert RAGSearchTool().definition.required_permission == "rag.search"

    @pytest.mark.asyncio
    async def test_missing_query_returns_failure(self) -> None:
        tool = RAGSearchTool()
        result = await tool.execute({"project_id": str(uuid4())}, _ctx(), _session())
        assert not result.success
        assert "query" in (result.error or "")

    @pytest.mark.asyncio
    async def test_missing_project_id_returns_failure(self) -> None:
        tool = RAGSearchTool()
        result = await tool.execute({"query": "hello"}, _ctx(), _session())
        assert not result.success

    @pytest.mark.asyncio
    async def test_no_permission_returns_failure(self) -> None:
        tool = RAGSearchTool()
        ctx = _ctx(frozenset())
        result = await tool.execute(
            {"query": "hello", "project_id": str(uuid4())}, ctx, _session()
        )
        assert not result.success
        assert "rag.search" in (result.error or "")

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_failure(self) -> None:
        tool = RAGSearchTool()
        result = await tool.execute(
            {"query": "hello", "project_id": "not-a-uuid"}, _ctx(), _session()
        )
        assert not result.success

    @pytest.mark.asyncio
    async def test_success_returns_results(self) -> None:
        session = _session()
        project_id = uuid4()
        ctx = _ctx()

        mock_chunk = MagicMock()
        mock_chunk.citation_label = "doc#chunk-0"
        mock_chunk.content = "The sky is blue."

        with (
            patch(
                "app.agent.tools.rag_search.OllamaEmbeddingProvider.embed",
                new=AsyncMock(return_value=[0.1] * 768),
            ),
            patch(
                "app.agent.tools.rag_search.DocumentChunkRepository.search_similar",
                new=AsyncMock(return_value=[(mock_chunk, "sky.txt")]),
            ),
        ):
            tool = RAGSearchTool()
            result = await tool.execute(
                {"query": "sky color", "project_id": str(project_id)},
                ctx,
                session,
            )

        assert result.success
        assert result.data["count"] == 1
        assert result.data["results"][0]["citation"] == "doc#chunk-0"


# ── TenantLookupTool ──────────────────────────────────────────────────────────


class TestTenantLookupTool:
    def test_definition_name(self) -> None:
        assert TenantLookupTool().definition.name == "tenant_lookup"

    def test_no_required_permission(self) -> None:
        assert TenantLookupTool().definition.required_permission is None

    @pytest.mark.asyncio
    async def test_tenant_not_found_returns_failure(self) -> None:
        session = _session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await TenantLookupTool().execute({}, _ctx(), session)
        assert not result.success
        assert "not found" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_returns_tenant_info(self) -> None:
        session = _session()
        mock_tenant = MagicMock()
        mock_tenant.name = "Acme Corp"
        mock_tenant.plan = "enterprise"
        mock_tenant.status = "active"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 42

        session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        result = await TenantLookupTool().execute(
            {"include_members": True}, _ctx(), session
        )
        assert result.success
        assert result.data["name"] == "Acme Corp"
        assert result.data["plan"] == "enterprise"
        assert result.data["member_count"] == 42


# ── SQLAirlockTool ────────────────────────────────────────────────────────────


class TestSQLAirlockTool:
    def test_definition_name(self) -> None:
        assert SQLAirlockTool().definition.name == "sql_query"

    def test_validate_select_passes(self) -> None:
        _validate_select_only("SELECT id, name FROM users WHERE tenant_id = '1'")

    def test_validate_blocks_insert(self) -> None:
        with pytest.raises(SqlAirlockViolation):
            _validate_select_only("INSERT INTO users VALUES (1, 'evil')")

    def test_validate_blocks_drop(self) -> None:
        with pytest.raises(SqlAirlockViolation):
            _validate_select_only("SELECT 1; DROP TABLE users;")

    def test_validate_blocks_empty(self) -> None:
        with pytest.raises(SqlAirlockViolation):
            _validate_select_only("")

    @pytest.mark.asyncio
    async def test_missing_sql_returns_failure(self) -> None:
        result = await SQLAirlockTool().execute({}, _ctx(), _session())
        assert not result.success

    @pytest.mark.asyncio
    async def test_no_permission_returns_failure(self) -> None:
        result = await SQLAirlockTool().execute(
            {"sql": "SELECT 1"}, _ctx(frozenset()), _session()
        )
        assert not result.success
        assert "analytics.read" in (result.error or "")

    @pytest.mark.asyncio
    async def test_blocked_sql_returns_failure(self) -> None:
        result = await SQLAirlockTool().execute(
            {"sql": "DELETE FROM users"}, _ctx(), _session()
        )
        assert not result.success
        assert "blocked" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_valid_select_returns_rows(self) -> None:
        session = _session()
        mock_result = MagicMock()
        mock_result.keys.return_value = ["id", "name"]
        mock_result.fetchall.return_value = [("abc", "Alice"), ("def", "Bob")]
        session.execute = AsyncMock(return_value=mock_result)

        result = await SQLAirlockTool().execute(
            {"sql": "SELECT id, name FROM tenants"}, _ctx(), session
        )
        assert result.success
        assert result.data["row_count"] == 2
        assert result.data["columns"] == ["id", "name"]


# ── RBACPolicyTool ────────────────────────────────────────────────────────────


class TestRBACPolicyTool:
    def test_definition_name(self) -> None:
        assert RBACPolicyTool().definition.name == "rbac_check"

    @pytest.mark.asyncio
    async def test_check_granted_permission(self) -> None:
        ctx = _ctx(frozenset({"rag.search", "agent.run"}))
        result = await RBACPolicyTool().execute(
            {"permission": "rag.search"}, ctx, _session()
        )
        assert result.success
        assert result.data["granted"] is True

    @pytest.mark.asyncio
    async def test_check_denied_permission(self) -> None:
        ctx = _ctx(frozenset({"rag.search"}))
        result = await RBACPolicyTool().execute(
            {"permission": "analytics.read"}, ctx, _session()
        )
        assert result.success
        assert result.data["granted"] is False

    @pytest.mark.asyncio
    async def test_list_all_permissions(self) -> None:
        ctx = _ctx(frozenset({"rag.search", "agent.run"}))
        result = await RBACPolicyTool().execute({}, ctx, _session())
        assert result.success
        assert "rag.search" in result.data["permissions"]
        assert "agent.run" in result.data["permissions"]


# ── AuditLogTool ──────────────────────────────────────────────────────────────


class TestAuditLogTool:
    def test_definition_name(self) -> None:
        assert AuditLogTool().definition.name == "audit_log"

    @pytest.mark.asyncio
    async def test_missing_action_returns_failure(self) -> None:
        result = await AuditLogTool().execute({}, _ctx(), _session())
        assert not result.success
        assert "action" in (result.error or "")

    @pytest.mark.asyncio
    async def test_creates_audit_event(self) -> None:
        session = _session()
        result = await AuditLogTool().execute(
            {
                "action": "document.accessed",
                "resource_type": "document",
                "details": "ok",
            },
            _ctx(),
            session,
        )
        assert result.success
        assert "event_id" in result.data
        assert result.data["action"] == "document.accessed"
        session.add.assert_called_once()
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_truncated_at_100_chars(self) -> None:
        session = _session()
        long_action = "a" * 200
        result = await AuditLogTool().execute({"action": long_action}, _ctx(), session)
        assert result.success
        # The event stored in session has truncated action
        added_event = session.add.call_args[0][0]
        assert len(added_event.action) == 100
