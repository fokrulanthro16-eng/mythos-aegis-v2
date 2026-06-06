"""HTTP-layer tests for the workflow router."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security_context import SecurityContext
from app.workflow.schemas import (
    ExecutionResponse,
    ExecutionSummaryResponse,
    WorkflowResponse,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _ctx(permissions: frozenset[str] | None = None) -> SecurityContext:
    if permissions is None:
        permissions = frozenset(
            {
                "workflow.create",
                "workflow.read",
                "workflow.execute",
                "workflow.admin",
            }
        )
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"admin"}),
        permissions=permissions,
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


@pytest.fixture
def client_read_only() -> Generator[TestClient, None, None]:
    yield from _make_client(_ctx(frozenset({"workflow.read"})))


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _wf_response(name: str = "Invoice Processing") -> WorkflowResponse:
    return WorkflowResponse(
        workflow_id=uuid4(),
        name=name,
        description="Processes invoices",
        version=1,
        is_active=True,
        step_count=2,
        created_at=_now(),
    )


def _exec_response(status: str = "completed") -> ExecutionResponse:
    return ExecutionResponse(
        execution_id=uuid4(),
        workflow_id=uuid4(),
        workflow_version=1,
        status=status,
        created_at=_now(),
        steps=[],
    )


def _valid_workflow_body(name: str = "Test Workflow") -> dict:
    return {
        "name": name,
        "description": "A test workflow",
        "steps": [
            {
                "id": "step1",
                "name": "First Step",
                "type": "transform",
                "config": {"output": {"result": "ok"}},
            }
        ],
    }


# ── POST /v1/workflows ────────────────────────────────────────────────────────


class TestCreateWorkflow:
    def test_create_returns_201(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.create_workflow = AsyncMock(return_value=_wf_response())

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.post("/v1/workflows", json=_valid_workflow_body())

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Invoice Processing"
        assert body["step_count"] == 2

    def test_create_returns_403_without_permission(
        self, client_no_perms: TestClient
    ) -> None:
        resp = client_no_perms.post("/v1/workflows", json=_valid_workflow_body())
        assert resp.status_code == 403

    def test_create_empty_name_rejected(self, client: TestClient) -> None:
        body = _valid_workflow_body()
        body["name"] = ""
        resp = client.post("/v1/workflows", json=body)
        assert resp.status_code == 422

    def test_create_empty_steps_rejected(self, client: TestClient) -> None:
        body = _valid_workflow_body()
        body["steps"] = []
        resp = client.post("/v1/workflows", json=body)
        assert resp.status_code == 422


# ── GET /v1/workflows ─────────────────────────────────────────────────────────


class TestListWorkflows:
    def test_list_returns_200(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.list_workflows = AsyncMock(
            return_value=[_wf_response("A"), _wf_response("B")]
        )

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.get("/v1/workflows")

        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_returns_403_without_read_permission(
        self, client_no_perms: TestClient
    ) -> None:
        resp = client_no_perms.get("/v1/workflows")
        assert resp.status_code == 403

    def test_list_empty_returns_empty_array(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.list_workflows = AsyncMock(return_value=[])

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.get("/v1/workflows")

        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /v1/workflows/{id} ────────────────────────────────────────────────────


class TestGetWorkflow:
    def test_get_returns_200(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.get_workflow = AsyncMock(return_value=_wf_response("Contract"))

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.get(f"/v1/workflows/{uuid4()}")

        assert resp.status_code == 200
        assert resp.json()["name"] == "Contract"

    def test_get_returns_404_not_found(self, client: TestClient) -> None:
        from app.core.exceptions import WorkflowNotFoundError

        svc = MagicMock()
        svc.get_workflow = AsyncMock(side_effect=WorkflowNotFoundError("not found"))

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.get(f"/v1/workflows/{uuid4()}")

        assert resp.status_code == 404

    def test_get_returns_403_without_read_permission(
        self, client_no_perms: TestClient
    ) -> None:
        resp = client_no_perms.get(f"/v1/workflows/{uuid4()}")
        assert resp.status_code == 403


# ── DELETE /v1/workflows/{id} ─────────────────────────────────────────────────


class TestDeactivateWorkflow:
    def test_deactivate_returns_200(self, client: TestClient) -> None:
        inactive = _wf_response()
        inactive.is_active = False
        svc = MagicMock()
        svc.deactivate_workflow = AsyncMock(return_value=inactive)

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.delete(f"/v1/workflows/{uuid4()}")

        assert resp.status_code == 200

    def test_deactivate_returns_403_without_admin_permission(
        self, client_read_only: TestClient
    ) -> None:
        resp = client_read_only.delete(f"/v1/workflows/{uuid4()}")
        assert resp.status_code == 403


# ── POST /v1/workflows/{id}/execute ──────────────────────────────────────────


class TestTriggerExecution:
    def test_execute_returns_200(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.trigger_execution = AsyncMock(return_value=_exec_response("completed"))

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.post(
                f"/v1/workflows/{uuid4()}/execute",
                json={"input": {"filename": "invoice.pdf"}},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_execute_returns_200_with_failed_status(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.trigger_execution = AsyncMock(return_value=_exec_response("failed"))

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.post(
                f"/v1/workflows/{uuid4()}/execute",
                json={"input": {}},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_execute_returns_403_without_permission(
        self, client_no_perms: TestClient
    ) -> None:
        resp = client_no_perms.post(
            f"/v1/workflows/{uuid4()}/execute", json={"input": {}}
        )
        assert resp.status_code == 403

    def test_execute_returns_404_for_unknown_workflow(self, client: TestClient) -> None:
        from app.core.exceptions import WorkflowNotFoundError

        svc = MagicMock()
        svc.trigger_execution = AsyncMock(
            side_effect=WorkflowNotFoundError("not found")
        )

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.post(f"/v1/workflows/{uuid4()}/execute", json={"input": {}})

        assert resp.status_code == 404

    def test_execute_returns_400_for_inactive_workflow(
        self, client: TestClient
    ) -> None:
        from app.core.exceptions import WorkflowError

        svc = MagicMock()
        svc.trigger_execution = AsyncMock(
            side_effect=WorkflowError("Workflow is not active")
        )

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.post(f"/v1/workflows/{uuid4()}/execute", json={"input": {}})

        assert resp.status_code == 400


# ── GET /v1/workflows/{id}/executions ────────────────────────────────────────


class TestListExecutions:
    def test_list_executions_returns_200(self, client: TestClient) -> None:
        wf_id = uuid4()
        summaries = [
            ExecutionSummaryResponse(
                execution_id=uuid4(),
                workflow_id=wf_id,
                status="completed",
                created_at=_now(),
            )
        ]
        svc = MagicMock()
        svc.list_executions = AsyncMock(return_value=summaries)

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.get(f"/v1/workflows/{wf_id}/executions")

        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ── GET /v1/workflows/executions/{exec_id} ────────────────────────────────────


class TestGetExecution:
    def test_get_execution_returns_200(self, client: TestClient) -> None:
        exec_id = uuid4()
        svc = MagicMock()
        svc.get_execution = AsyncMock(return_value=_exec_response("completed"))

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.get(f"/v1/workflows/executions/{exec_id}")

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_get_execution_returns_404(self, client: TestClient) -> None:
        from app.core.exceptions import WorkflowNotFoundError

        svc = MagicMock()
        svc.get_execution = AsyncMock(side_effect=WorkflowNotFoundError("not found"))

        with patch("app.workflow.routes.WorkflowService", return_value=svc):
            resp = client.get(f"/v1/workflows/executions/{uuid4()}")

        assert resp.status_code == 404

    def test_get_execution_returns_403_without_permission(
        self, client_no_perms: TestClient
    ) -> None:
        resp = client_no_perms.get(f"/v1/workflows/executions/{uuid4()}")
        assert resp.status_code == 403
