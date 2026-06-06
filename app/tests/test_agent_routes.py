"""Integration tests for the agent API routes.

Uses the same JWT middleware bypass pattern established in test_rag_routes.py:
  - patch validate_token + build_security_context in the middleware
  - include Authorization: Bearer test-token header
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security_context import SecurityContext


def _ctx(permissions: frozenset[str] | None = None) -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"admin"}),
        permissions=(
            permissions
            if permissions is not None
            else frozenset(
                {
                    "agent.run",
                    "agent.sessions.read",
                    "agent.sessions.write",
                    "rag.search",
                    "analytics.read",
                }
            )
        ),
    )


def _make_client(ctx: SecurityContext) -> Generator[TestClient, None, None]:
    from app.auth.dependencies import get_security_context
    from app.db.session import get_session
    from app.main import app

    app.dependency_overrides[get_security_context] = lambda: ctx
    app.dependency_overrides[get_session] = lambda: AsyncMock()

    with (
        patch("app.auth.middleware.validate_token", return_value={}),
        patch("app.auth.middleware.build_security_context", return_value=ctx),
    ):
        yield TestClient(
            app,
            raise_server_exceptions=False,
            headers={"Authorization": "Bearer test-token"},
        )

    app.dependency_overrides.clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    yield from _make_client(_ctx())


@pytest.fixture
def client_no_perms() -> Generator[TestClient, None, None]:
    yield from _make_client(_ctx(frozenset()))


# ── GET /v1/agent/tools ───────────────────────────────────────────────────────


class TestListTools:
    def test_returns_tool_list(self, client: TestClient) -> None:
        r = client.get("/v1/agent/tools")
        assert r.status_code == 200
        tools = r.json()
        names = [t["name"] for t in tools]
        assert "rag_search" in names
        assert "tenant_lookup" in names
        assert "sql_query" in names
        assert "rbac_check" in names
        assert "audit_log" in names

    def test_requires_agent_run_permission(self, client_no_perms: TestClient) -> None:
        r = client_no_perms.get("/v1/agent/tools")
        assert r.status_code == 403

    def test_tool_has_required_fields(self, client: TestClient) -> None:
        r = client.get("/v1/agent/tools")
        assert r.status_code == 200
        tool = r.json()[0]
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool


# ── POST /v1/agent/run ────────────────────────────────────────────────────────


class TestRunAgent:
    def test_returns_answer(self, client: TestClient) -> None:
        mock_response = MagicMock()
        mock_response.answer = "The answer is 42."
        mock_response.tool_calls = []
        mock_response.iterations = 1
        mock_response.session_id = None

        with patch(
            "app.agent.routes.AgentOrchestrator.run_stateless",
            new=AsyncMock(return_value=mock_response),
        ):
            r = client.post(
                "/v1/agent/run",
                json={
                    "project_id": str(uuid4()),
                    "question": "What is the answer?",
                },
            )

        assert r.status_code == 200
        body = r.json()
        assert body["answer"] == "The answer is 42."
        assert body["iterations"] == 1

    def test_requires_agent_run_permission(self, client_no_perms: TestClient) -> None:
        r = client_no_perms.post(
            "/v1/agent/run",
            json={"project_id": str(uuid4()), "question": "test"},
        )
        assert r.status_code == 403

    def test_invalid_question_returns_422(self, client: TestClient) -> None:
        r = client.post(
            "/v1/agent/run",
            json={"project_id": str(uuid4()), "question": ""},
        )
        assert r.status_code == 422

    def test_missing_project_id_returns_422(self, client: TestClient) -> None:
        r = client.post("/v1/agent/run", json={"question": "test"})
        assert r.status_code == 422


# ── POST /v1/agent/sessions ───────────────────────────────────────────────────


class TestCreateSession:
    def test_creates_session(self, client: TestClient) -> None:
        from datetime import datetime

        mock_session = MagicMock()
        mock_session.id = uuid4()
        mock_session.project_id = uuid4()
        mock_session.title = "Test session"
        mock_session.created_at = datetime.now(UTC)

        with patch(
            "app.agent.routes.AgentOrchestrator.create_session",
            new=AsyncMock(return_value=mock_session),
        ):
            r = client.post(
                "/v1/agent/sessions",
                json={"project_id": str(uuid4()), "title": "Test session"},
            )

        assert r.status_code == 201
        body = r.json()
        assert "session_id" in body
        assert body["title"] == "Test session"

    def test_requires_sessions_write_permission(
        self, client_no_perms: TestClient
    ) -> None:
        r = client_no_perms.post(
            "/v1/agent/sessions",
            json={"project_id": str(uuid4())},
        )
        assert r.status_code == 403


# ── POST /v1/agent/sessions/{id}/chat ────────────────────────────────────────


class TestChat:
    def test_returns_chat_response(self, client: TestClient) -> None:
        session_id = uuid4()
        mock_session_obj = MagicMock()
        mock_session_obj.id = session_id

        mock_response = MagicMock()
        mock_response.answer = "Hello from agent."
        mock_response.session_id = session_id
        mock_response.tool_calls = []
        mock_response.iterations = 1

        with (
            patch(
                "app.agent.routes.AgentOrchestrator.get_session",
                new=AsyncMock(return_value=mock_session_obj),
            ),
            patch(
                "app.agent.routes.AgentOrchestrator.run_in_session",
                new=AsyncMock(return_value=mock_response),
            ),
        ):
            r = client.post(
                f"/v1/agent/sessions/{session_id}/chat",
                json={"message": "Hello"},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["answer"] == "Hello from agent."

    def test_session_not_found_returns_404(self, client: TestClient) -> None:
        with patch(
            "app.agent.routes.AgentOrchestrator.get_session",
            new=AsyncMock(return_value=None),
        ):
            r = client.post(
                f"/v1/agent/sessions/{uuid4()}/chat",
                json={"message": "Hello"},
            )
        assert r.status_code == 404


# ── GET /v1/agent/sessions/{id} ───────────────────────────────────────────────


class TestGetSessionHistory:
    def test_returns_history(self, client: TestClient) -> None:
        from datetime import datetime

        session_id = uuid4()
        mock_session_obj = MagicMock()
        mock_session_obj.id = session_id
        mock_session_obj.title = "My session"

        mock_msg = MagicMock()
        mock_msg.id = uuid4()
        mock_msg.role = "user"
        mock_msg.content = "Hi"
        mock_msg.tool_name = None
        mock_msg.created_at = datetime.now(UTC)

        with (
            patch(
                "app.agent.routes.AgentOrchestrator.get_session",
                new=AsyncMock(return_value=mock_session_obj),
            ),
            patch(
                "app.agent.memory.ConversationMemory.get_messages",
                new=AsyncMock(return_value=[mock_msg]),
            ),
        ):
            r = client.get(f"/v1/agent/sessions/{session_id}")

        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "My session"
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "user"

    def test_session_not_found_returns_404(self, client: TestClient) -> None:
        with patch(
            "app.agent.routes.AgentOrchestrator.get_session",
            new=AsyncMock(return_value=None),
        ):
            r = client.get(f"/v1/agent/sessions/{uuid4()}")
        assert r.status_code == 404

    def test_requires_sessions_read_permission(
        self, client_no_perms: TestClient
    ) -> None:
        r = client_no_perms.get(f"/v1/agent/sessions/{uuid4()}")
        assert r.status_code == 403
