"""Agent orchestrator — ties together memory, runtime, and sessions."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import AgentLLMClient
from app.agent.memory import ConversationMemory
from app.agent.prompt_builder import build_system_prompt, format_tool_result
from app.agent.runtime import AgentRuntime
from app.agent.schemas import AgentRunResponse, ChatResponse
from app.agent.tools.registry import ToolRegistry, get_registry
from app.core.security_context import SecurityContext
from app.db.models.agent_session import AgentSession

logger = logging.getLogger(__name__)

_MAX_CONTEXT_CHARS = 8_000


class AgentOrchestrator:
    """High-level orchestration for stateless and stateful agent interactions."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        llm: AgentLLMClient | None = None,
    ) -> None:
        self._registry = registry or get_registry()
        self._llm = llm or AgentLLMClient()
        self._runtime = AgentRuntime(self._registry, self._llm)

    # ── Session management ────────────────────────────────────────────────────

    async def create_session(
        self,
        db_session: AsyncSession,
        *,
        tenant_id: UUID,
        project_id: UUID,
        user_id: UUID,
        title: str = "New conversation",
    ) -> AgentSession:
        session = AgentSession(
            id=uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            title=title,
        )
        db_session.add(session)
        await db_session.flush()
        logger.info("agent.session.created id=%s tenant=%s", session.id, tenant_id)
        return session

    async def get_session(
        self,
        db_session: AsyncSession,
        *,
        session_id: UUID,
        tenant_id: UUID,
    ) -> AgentSession | None:
        result = await db_session.execute(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.tenant_id == tenant_id,
                AgentSession.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    # ── Single-turn (stateless) ───────────────────────────────────────────────

    async def run_stateless(
        self,
        db_session: AsyncSession,
        *,
        question: str,
        project_id: UUID,
        ctx: SecurityContext,
        max_iterations: int = 5,
    ) -> AgentRunResponse:
        """Run a single-turn agent call without persisting a session."""
        system_prompt = build_system_prompt(self._registry)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        result = await self._runtime.run_turn(
            messages, ctx, db_session, max_iterations=max_iterations
        )
        return AgentRunResponse(
            answer=result.answer,
            tool_calls=result.tool_calls,
            iterations=result.iterations,
        )

    # ── Multi-turn (stateful) ────────────────────────────────────────────────

    async def run_in_session(
        self,
        db_session: AsyncSession,
        *,
        session_id: UUID,
        message: str,
        ctx: SecurityContext,
        max_iterations: int = 5,
    ) -> ChatResponse:
        """Send a message in an existing session, preserving history."""
        memory = ConversationMemory(db_session, session_id, ctx.tenant_id)
        await memory.add_message("user", message)

        system_prompt = build_system_prompt(self._registry)
        history = await memory.to_llm_messages(max_chars=_MAX_CONTEXT_CHARS)
        messages = [{"role": "system", "content": system_prompt}, *history]

        result = await self._runtime.run_turn(
            messages, ctx, db_session, max_iterations=max_iterations
        )

        # Persist tool call records as tool messages
        for tc in result.tool_calls:
            await memory.add_message(
                "tool",
                format_tool_result(tc.tool_name, tc.success, None, tc.error),
                tool_name=tc.tool_name,
                tool_input=tc.params,
                tool_output={"success": tc.success, "error": tc.error},
            )

        await memory.add_message("assistant", result.answer)

        return ChatResponse(
            answer=result.answer,
            session_id=session_id,
            tool_calls=result.tool_calls,
            iterations=result.iterations,
        )
