"""Unit tests for the workflow step executor."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import WorkflowStepError
from app.core.security_context import SecurityContext
from app.workflow.executor import StepExecutor
from app.workflow.models import RetryConfig, StepDefinition, StepType


def _ctx() -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"admin"}),
        permissions=frozenset(
            {
                "workflow.execute",
                "agent.run",
                "rag.search",
                "rag.upload",
                "vision.analyze",
                "vision.extract",
            }
        ),
    )


def _session() -> AsyncMock:
    return AsyncMock()


def _step(step_type: StepType, config: dict | None = None) -> StepDefinition:
    return StepDefinition(
        id="test_step",
        name="Test Step",
        type=step_type,
        config=config or {},
        retry=RetryConfig(max_attempts=1),
    )


def _context(extra_input: dict | None = None) -> dict:
    return {
        "input": {"project_id": str(uuid4()), **(extra_input or {})},
        "steps": {},
    }


# ── TRANSFORM ─────────────────────────────────────────────────────────────────


class TestTransformStep:
    @pytest.mark.asyncio
    async def test_returns_output_dict(self) -> None:
        executor = StepExecutor()
        step = _step(StepType.TRANSFORM, {"output": {"key": "value"}})
        ctx = _context()

        result = await executor.execute(step, ctx, _ctx(), _session())
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_output_with_resolved_template(self) -> None:
        executor = StepExecutor()
        pid = str(uuid4())
        step = _step(
            StepType.TRANSFORM,
            {"output": {"project": "{{ input.project_id }}"}},
        )
        ctx_data = _context({"project_id": pid})

        result = await executor.execute(step, ctx_data, _ctx(), _session())
        assert result["project"] == pid

    @pytest.mark.asyncio
    async def test_missing_output_key_raises(self) -> None:
        executor = StepExecutor()
        step = _step(StepType.TRANSFORM, {})

        with pytest.raises(WorkflowStepError, match="output"):
            await executor.execute(step, _context(), _ctx(), _session())

    @pytest.mark.asyncio
    async def test_non_dict_output_raises(self) -> None:
        executor = StepExecutor()
        step = _step(StepType.TRANSFORM, {"output": "not a dict"})

        with pytest.raises(WorkflowStepError, match="output"):
            await executor.execute(step, _context(), _ctx(), _session())


# ── AGENT_TASK ────────────────────────────────────────────────────────────────


class TestAgentTaskStep:
    @pytest.mark.asyncio
    async def test_calls_orchestrator_and_returns_answer(self) -> None:
        executor = StepExecutor()
        pid = str(uuid4())
        step = _step(
            StepType.AGENT_TASK,
            {"prompt": "Summarize the document.", "project_id": pid},
        )

        mock_result = MagicMock()
        mock_result.answer = "Summary: the document is about AI."
        mock_result.iterations = 2
        mock_result.tool_calls = []

        mock_orch = AsyncMock()
        mock_orch.run_stateless = AsyncMock(return_value=mock_result)

        with patch(
            "app.agent.orchestrator.AgentOrchestrator",
            return_value=mock_orch,
        ):
            result = await executor.execute(
                step, _context({"project_id": pid}), _ctx(), _session()
            )

        assert result["answer"] == "Summary: the document is about AI."
        assert result["iterations"] == 2

    @pytest.mark.asyncio
    async def test_empty_prompt_raises(self) -> None:
        executor = StepExecutor()
        step = _step(StepType.AGENT_TASK, {"prompt": ""})

        with pytest.raises(WorkflowStepError, match="prompt"):
            await executor.execute(step, _context(), _ctx(), _session())

    @pytest.mark.asyncio
    async def test_missing_prompt_raises(self) -> None:
        executor = StepExecutor()
        step = _step(StepType.AGENT_TASK, {})

        with pytest.raises(WorkflowStepError, match="prompt"):
            await executor.execute(step, _context(), _ctx(), _session())


# ── RAG_SEARCH ────────────────────────────────────────────────────────────────


class TestRAGSearchStep:
    @pytest.mark.asyncio
    async def test_returns_results(self) -> None:
        executor = StepExecutor()
        pid = str(uuid4())
        step = _step(
            StepType.RAG_SEARCH,
            {"query": "contract termination clause", "project_id": pid},
        )

        from app.core.result import Success
        from app.rag.schemas import ChunkResult, SearchResponse

        mock_chunk = ChunkResult(
            document_id=uuid4(),
            filename="contract.pdf",
            chunk_index=4,
            citation_label="contract#chunk-4",
            excerpt="Clause 12: termination requires 30 days.",
        )

        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(
            return_value=Success(SearchResponse(results=[mock_chunk], query_chars=30))
        )

        with patch("app.rag.service.RAGService", return_value=mock_svc):
            result = await executor.execute(
                step, _context({"project_id": pid}), _ctx(), _session()
            )

        assert result["count"] == 1
        assert result["results"][0]["citation_label"] == "contract#chunk-4"

    @pytest.mark.asyncio
    async def test_empty_query_raises(self) -> None:
        executor = StepExecutor()
        step = _step(
            StepType.RAG_SEARCH,
            {"query": "", "project_id": str(uuid4())},
        )

        with pytest.raises(WorkflowStepError, match="query"):
            await executor.execute(step, _context(), _ctx(), _session())

    @pytest.mark.asyncio
    async def test_rag_failure_raises_step_error(self) -> None:
        executor = StepExecutor()
        pid = str(uuid4())
        step = _step(
            StepType.RAG_SEARCH,
            {"query": "search query", "project_id": pid},
        )

        from app.core.exceptions import EmbeddingError
        from app.core.result import Failure

        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(
            return_value=Failure(
                error=EmbeddingError("Ollama down"),
                message="Embedding service unavailable",
            )
        )

        with (
            patch("app.rag.service.RAGService", return_value=mock_svc),
            pytest.raises(WorkflowStepError, match="RAG search failed"),
        ):
            await executor.execute(
                step, _context({"project_id": pid}), _ctx(), _session()
            )


# ── RAG_INDEX ─────────────────────────────────────────────────────────────────


class TestRAGIndexStep:
    @pytest.mark.asyncio
    async def test_indexes_text_and_returns_document_id(self) -> None:
        executor = StepExecutor()
        pid = str(uuid4())
        doc_id = uuid4()
        step = _step(
            StepType.RAG_INDEX,
            {
                "text": "Invoice total: $1,200",
                "filename": "invoice.txt",
                "project_id": pid,
            },
        )

        from app.core.result import Success
        from app.rag.schemas import DocumentUploadResponse

        mock_svc = MagicMock()
        mock_svc.upload_document = AsyncMock(
            return_value=Success(
                DocumentUploadResponse(
                    document_id=doc_id,
                    filename="invoice.txt",
                    status="indexed",
                    chunk_count=3,
                )
            )
        )

        with patch("app.rag.service.RAGService", return_value=mock_svc):
            result = await executor.execute(
                step, _context({"project_id": pid}), _ctx(), _session()
            )

        assert result["status"] == "indexed"
        assert result["chunk_count"] == 3

    @pytest.mark.asyncio
    async def test_empty_text_raises(self) -> None:
        executor = StepExecutor()
        step = _step(
            StepType.RAG_INDEX,
            {"text": "", "project_id": str(uuid4())},
        )

        with pytest.raises(WorkflowStepError, match="text"):
            await executor.execute(step, _context(), _ctx(), _session())


# ── VISION_ANALYZE ────────────────────────────────────────────────────────────


class TestVisionAnalyzeStep:
    @pytest.mark.asyncio
    async def test_decodes_base64_and_returns_analysis(self) -> None:
        executor = StepExecutor()
        image_b64 = base64.b64encode(b"\x89PNG fake").decode()
        pid = str(uuid4())
        step = _step(
            StepType.VISION_ANALYZE,
            {
                "file_base64": image_b64,
                "filename": "chart.png",
                "prompt": "Describe the chart.",
                "project_id": pid,
            },
        )

        from app.vision.schemas import VisionAnalyzeResponse

        mock_result = VisionAnalyzeResponse(
            analysis="A bar chart showing Q1 revenue.",
            model="qwen2.5-vl:7b",
            filename="chart.png",
            file_type="image/png",
        )
        mock_svc = MagicMock()
        mock_svc.analyze_image = AsyncMock(return_value=mock_result)

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            result = await executor.execute(
                step, _context({"project_id": pid}), _ctx(), _session()
            )

        assert result["analysis"] == "A bar chart showing Q1 revenue."
        assert result["file_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_missing_file_base64_raises(self) -> None:
        executor = StepExecutor()
        step = _step(StepType.VISION_ANALYZE, {"filename": "img.png"})

        with pytest.raises(WorkflowStepError, match="file_base64"):
            await executor.execute(step, _context(), _ctx(), _session())

    @pytest.mark.asyncio
    async def test_invalid_base64_raises(self) -> None:
        executor = StepExecutor()
        step = _step(
            StepType.VISION_ANALYZE,
            {"file_base64": "!!not valid!!", "filename": "img.png"},
        )

        with pytest.raises(WorkflowStepError, match="base64"):
            await executor.execute(step, _context(), _ctx(), _session())


# ── VISION_EXTRACT ────────────────────────────────────────────────────────────


class TestVisionExtractStep:
    @pytest.mark.asyncio
    async def test_extracts_pdf_and_returns_text(self) -> None:
        executor = StepExecutor()
        pdf_b64 = base64.b64encode(b"%PDF-1.4 fake").decode()
        pid = str(uuid4())
        step = _step(
            StepType.VISION_EXTRACT,
            {
                "file_base64": pdf_b64,
                "filename": "contract.pdf",
                "project_id": pid,
            },
        )

        from app.vision.schemas import PDFExtractResponse

        mock_result = PDFExtractResponse(
            filename="contract.pdf",
            page_count=2,
            text_pages=["Page 1 text.", "Page 2 text."],
            total_chars=24,
        )
        mock_svc = MagicMock()
        mock_svc.extract_pdf = AsyncMock(return_value=mock_result)

        with patch("app.vision.service.VisionService", return_value=mock_svc):
            result = await executor.execute(
                step, _context({"project_id": pid}), _ctx(), _session()
            )

        assert result["page_count"] == 2
        assert result["total_chars"] == 24
        assert "Page 1 text." in result["text"]

    @pytest.mark.asyncio
    async def test_missing_file_base64_raises(self) -> None:
        executor = StepExecutor()
        step = _step(StepType.VISION_EXTRACT, {"filename": "doc.pdf"})

        with pytest.raises(WorkflowStepError, match="file_base64"):
            await executor.execute(step, _context(), _ctx(), _session())


# ── Unknown step type ─────────────────────────────────────────────────────────


class TestUnknownStepType:
    @pytest.mark.asyncio
    async def test_unknown_type_raises(self) -> None:
        executor = StepExecutor()
        step = StepDefinition(
            id="bad",
            name="Bad",
            type=StepType.TRANSFORM,
            config={"output": {}},
        )
        # Manually override type to something unsupported via object mutation
        object.__setattr__(step, "type", "unknown_type")  # type: ignore[arg-type]

        with pytest.raises((WorkflowStepError, Exception)):
            await executor.execute(step, _context(), _ctx(), _session())
