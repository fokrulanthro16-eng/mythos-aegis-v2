"""Step executor — dispatches each workflow step to the correct service.

Supported step types
---------------------
agent_task      — stateless agent run via AgentOrchestrator
rag_search      — semantic search via RAGService
rag_index       — index text content via RAGService
vision_analyze  — image analysis via VisionService
vision_extract  — PDF text extraction via VisionService
transform       — template-based data remapping (no external service call)

Security
--------
- No prompt or document content is logged.
- Base64 image bytes are decoded in memory; length logged, not content.
- project_id is always sourced from the validated SecurityContext or the
  explicit ``project_id`` field in step config.
"""

from __future__ import annotations

import base64
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ImageTooLargeError,
    UnsupportedFileTypeError,
    WorkflowStepError,
)
from app.core.security_context import SecurityContext
from app.workflow.models import StepDefinition, StepType
from app.workflow.templates import resolve, resolve_dict

logger = logging.getLogger(__name__)


def _parse_uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError) as exc:
        raise WorkflowStepError(f"Invalid UUID for field '{field}': {value!r}") from exc


class StepExecutor:
    """Execute a single workflow step against the appropriate service."""

    async def execute(
        self,
        step: StepDefinition,
        context: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Resolve templates in step config, then dispatch to handler."""
        resolved = resolve_dict(step.config, context)

        logger.debug(
            "workflow.step.execute type=%s step_id=%s tenant=%s",
            step.type,
            step.id,
            ctx.tenant_id,
        )

        match step.type:
            case StepType.AGENT_TASK:
                return await self._agent_task(resolved, ctx, session)
            case StepType.RAG_SEARCH:
                return await self._rag_search(resolved, ctx, session)
            case StepType.RAG_INDEX:
                return await self._rag_index(resolved, ctx, session)
            case StepType.VISION_ANALYZE:
                return await self._vision_analyze(resolved, ctx, session)
            case StepType.VISION_EXTRACT:
                return await self._vision_extract(resolved, ctx, session)
            case StepType.TRANSFORM:
                return self._transform(resolved)
            case _:
                raise WorkflowStepError(f"Unknown step type: {step.type}")

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _agent_task(
        self,
        config: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        prompt = str(config.get("prompt", "")).strip()
        if not prompt:
            raise WorkflowStepError("agent_task requires a non-empty 'prompt'")

        raw_pid = str(config.get("project_id", "")).strip()
        project_id = _parse_uuid(raw_pid, "project_id") if raw_pid else None

        max_iter = int(config.get("max_iterations", 5))

        from app.agent.orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        result = await orch.run_stateless(
            session,
            question=prompt,
            project_id=project_id or ctx.tenant_id,
            ctx=ctx,
            max_iterations=max_iter,
        )

        logger.info(
            "workflow.step.agent_task.done iterations=%d tenant=%s",
            result.iterations,
            ctx.tenant_id,
        )

        return {
            "answer": result.answer,
            "iterations": result.iterations,
            "tool_calls": len(result.tool_calls),
        }

    async def _rag_search(
        self,
        config: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        query = str(config.get("query", "")).strip()
        if not query:
            raise WorkflowStepError("rag_search requires a non-empty 'query'")

        raw_pid = str(config.get("project_id", "")).strip()
        project_id = _parse_uuid(raw_pid, "project_id")

        top_k = int(config.get("top_k", 5))

        from app.core.result import Success
        from app.rag.schemas import SearchRequest
        from app.rag.service import RAGService

        svc = RAGService(session)
        req = SearchRequest(project_id=project_id, query=query, top_k=top_k)
        outcome = await svc.search(req, ctx)

        if isinstance(outcome, Success):
            results = outcome.value.results
            return {
                "results": [
                    {
                        "document_id": str(r.document_id),
                        "filename": r.filename,
                        "chunk_index": r.chunk_index,
                        "citation_label": r.citation_label,
                        "excerpt": r.excerpt,
                    }
                    for r in results
                ],
                "count": len(results),
            }
        raise WorkflowStepError(f"RAG search failed: {outcome.message}")

    async def _rag_index(
        self,
        config: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        text = str(config.get("text", "")).strip()
        if not text:
            raise WorkflowStepError("rag_index requires non-empty 'text'")

        filename = str(config.get("filename", "workflow_output.txt")).strip()
        raw_pid = str(config.get("project_id", "")).strip()
        project_id = _parse_uuid(raw_pid, "project_id")

        from app.core.result import Success
        from app.rag.service import RAGService

        svc = RAGService(session)
        outcome = await svc.upload_document(
            file_bytes=text.encode("utf-8"),
            filename=filename,
            project_id=project_id,
            ctx=ctx,
        )

        if isinstance(outcome, Success):
            return {
                "document_id": str(outcome.value.document_id),
                "status": outcome.value.status,
                "chunk_count": outcome.value.chunk_count,
            }
        raise WorkflowStepError(f"RAG indexing failed: {outcome.message}")

    async def _vision_analyze(
        self,
        config: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        file_b64 = str(config.get("file_base64", "")).strip()
        filename = str(config.get("filename", "image.png")).strip()
        prompt = str(config.get("prompt", "")).strip() or None

        if not file_b64:
            raise WorkflowStepError(
                "vision_analyze requires 'file_base64' in step config"
            )

        try:
            file_bytes = base64.b64decode(file_b64, validate=True)
        except Exception as exc:
            raise WorkflowStepError("'file_base64' is not valid base64") from exc

        raw_pid = str(config.get("project_id", "")).strip()
        project_id = _parse_uuid(raw_pid, "project_id") if raw_pid else None

        logger.debug(
            "workflow.step.vision_analyze bytes=%d tenant=%s",
            len(file_bytes),
            ctx.tenant_id,
        )

        try:
            from app.vision.service import VisionService

            svc = VisionService(session)
            result = await svc.analyze_image(
                file_bytes=file_bytes,
                filename=filename,
                ctx=ctx,
                prompt=prompt,
                project_id=project_id,
                index_into_rag=bool(config.get("index_into_rag", False)),
            )
        except (UnsupportedFileTypeError, ImageTooLargeError) as exc:
            raise WorkflowStepError(exc.message) from exc

        return {
            "analysis": result.analysis,
            "model": result.model,
            "filename": result.filename,
            "file_type": result.file_type,
        }

    async def _vision_extract(
        self,
        config: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        file_b64 = str(config.get("file_base64", "")).strip()
        filename = str(config.get("filename", "document.pdf")).strip()

        if not file_b64:
            raise WorkflowStepError(
                "vision_extract requires 'file_base64' in step config"
            )

        try:
            file_bytes = base64.b64decode(file_b64, validate=True)
        except Exception as exc:
            raise WorkflowStepError("'file_base64' is not valid base64") from exc

        raw_pid = str(config.get("project_id", "")).strip()
        project_id = _parse_uuid(raw_pid, "project_id") if raw_pid else None

        logger.debug(
            "workflow.step.vision_extract bytes=%d tenant=%s",
            len(file_bytes),
            ctx.tenant_id,
        )

        try:
            from app.vision.service import VisionService

            svc = VisionService(session)
            result = await svc.extract_pdf(
                pdf_bytes=file_bytes,
                filename=filename,
                ctx=ctx,
                project_id=project_id,
                index_into_rag=bool(config.get("index_into_rag", True)),
            )
        except (UnsupportedFileTypeError, ImageTooLargeError) as exc:
            raise WorkflowStepError(exc.message) from exc

        return {
            "filename": result.filename,
            "page_count": result.page_count,
            "text": "\n\n".join(result.text_pages),
            "total_chars": result.total_chars,
        }

    def _transform(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return the ``output`` sub-dict from config (already template-resolved)."""
        if "output" not in config:
            raise WorkflowStepError(
                "transform step requires an 'output' dict in its config"
            )
        output = config["output"]
        if not isinstance(output, dict):
            raise WorkflowStepError(
                "transform step requires an 'output' dict in its config"
            )
        return dict(output)

    # ── Template convenience ──────────────────────────────────────────────────

    @staticmethod
    def resolve_string(template: str, context: dict[str, Any]) -> str:
        return resolve(template, context)
