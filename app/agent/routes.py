"""Agent API endpoints.

All endpoints require a Bearer JWT.

Routes:
  GET  /v1/agent/tools                      — list available tools
  POST /v1/agent/run                        — stateless single-turn run
  POST /v1/agent/sessions                   — create multi-turn session
  POST /v1/agent/sessions/{id}/chat         — send message in session
  GET  /v1/agent/sessions/{id}              — get session history
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory import ConversationMemory
from app.agent.orchestrator import AgentOrchestrator
from app.agent.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ChatRequest,
    ChatResponse,
    CreateSessionRequest,
    MessageResponse,
    SessionHistoryResponse,
    SessionResponse,
    ToolDefinitionSchema,
    ToolParameterSchema,
)
from app.agent.tools.registry import get_registry
from app.auth.dependencies import get_security_context
from app.core.security_context import SecurityContext
from app.db.session import get_session

router = APIRouter(prefix="/v1/agent", tags=["agent"])

_SecurityCtx = Annotated[SecurityContext, Depends(get_security_context)]
_DbSession = Annotated[AsyncSession, Depends(get_session)]

_PERM_RUN = "agent.run"
_PERM_SESSIONS_READ = "agent.sessions.read"
_PERM_SESSIONS_WRITE = "agent.sessions.write"


def _require(ctx: SecurityContext, perm: str) -> None:
    if perm not in ctx.permissions:
        raise HTTPException(status_code=403, detail=f"Permission '{perm}' is required")


# ── Tool catalogue ────────────────────────────────────────────────────────────


@router.get("/tools", response_model=list[ToolDefinitionSchema])
async def list_tools(ctx: _SecurityCtx) -> list[ToolDefinitionSchema]:
    """List all available agent tools and their parameter schemas.

    Permission: agent.run
    """
    _require(ctx, _PERM_RUN)
    registry = get_registry()
    return [
        ToolDefinitionSchema(
            name=d.name,
            description=d.description,
            parameters={
                p.name: ToolParameterSchema(
                    type=p.type,
                    description=p.description,
                    default=p.default,
                )
                for p in d.parameters
            },
            required=[p.name for p in d.parameters if p.required],
            required_permission=d.required_permission,
        )
        for d in registry.list_definitions()
    ]


# ── Stateless run ─────────────────────────────────────────────────────────────


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    req: AgentRunRequest,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> AgentRunResponse:
    """Run a single-turn agent call.

    The agent may invoke tools to answer the question. No session is persisted.

    Permission: agent.run
    """
    _require(ctx, _PERM_RUN)
    orchestrator = AgentOrchestrator()
    return await orchestrator.run_stateless(
        session,
        question=req.question,
        project_id=req.project_id,
        ctx=ctx,
        max_iterations=req.max_iterations,
    )


# ── Sessions ──────────────────────────────────────────────────────────────────


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    req: CreateSessionRequest,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> SessionResponse:
    """Create a new multi-turn agent session.

    Permission: agent.sessions.write
    """
    _require(ctx, _PERM_SESSIONS_WRITE)
    orchestrator = AgentOrchestrator()
    agent_session = await orchestrator.create_session(
        session,
        tenant_id=ctx.tenant_id,
        project_id=req.project_id,
        user_id=ctx.current_user_id,
        title=req.title,
    )
    return SessionResponse(
        session_id=agent_session.id,
        project_id=agent_session.project_id,
        title=agent_session.title,
        created_at=agent_session.created_at,
    )


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat(
    session_id: UUID,
    req: ChatRequest,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> ChatResponse:
    """Send a message within an existing session.

    Conversation history is loaded from the DB and fed to the LLM, then
    the new messages (user, tool results, assistant) are persisted.

    Permission: agent.run + agent.sessions.write
    """
    _require(ctx, _PERM_RUN)
    _require(ctx, _PERM_SESSIONS_WRITE)

    orchestrator = AgentOrchestrator()
    agent_session = await orchestrator.get_session(
        session, session_id=session_id, tenant_id=ctx.tenant_id
    )
    if agent_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return await orchestrator.run_in_session(
        session,
        session_id=session_id,
        message=req.message,
        ctx=ctx,
        max_iterations=req.max_iterations,
    )


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
async def get_session_history(
    session_id: UUID,
    ctx: _SecurityCtx,
    session: _DbSession,
) -> SessionHistoryResponse:
    """Return the full message history for a session.

    Permission: agent.sessions.read
    """
    _require(ctx, _PERM_SESSIONS_READ)

    orchestrator = AgentOrchestrator()
    agent_session = await orchestrator.get_session(
        session, session_id=session_id, tenant_id=ctx.tenant_id
    )
    if agent_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    memory = ConversationMemory(session, session_id, ctx.tenant_id)
    messages = await memory.get_messages()

    return SessionHistoryResponse(
        session_id=session_id,
        title=agent_session.title,
        messages=[
            MessageResponse(
                message_id=msg.id,
                role=msg.role,
                content=msg.content,
                tool_name=msg.tool_name,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
    )
