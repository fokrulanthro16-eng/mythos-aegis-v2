"""Conversation memory service — DB-backed per-session message history.

Message content is never logged — only character counts and message counts.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_message import AgentMessage

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Manages the message history for one agent session."""

    def __init__(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        tenant_id: UUID,
    ) -> None:
        self._db = db_session
        self._session_id = session_id
        self._tenant_id = tenant_id

    async def add_message(
        self,
        role: str,
        content: str,
        *,
        tool_name: str | None = None,
        tool_input: dict[str, Any] | None = None,
        tool_output: dict[str, Any] | None = None,
    ) -> AgentMessage:
        msg = AgentMessage(
            id=uuid4(),
            session_id=self._session_id,
            tenant_id=self._tenant_id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_input=json.dumps(tool_input) if tool_input is not None else None,
            tool_output=json.dumps(tool_output) if tool_output is not None else None,
        )
        self._db.add(msg)
        await self._db.flush()
        logger.debug(
            "memory.add role=%s session=%s content_chars=%d",
            role,
            self._session_id,
            len(content),
        )
        return msg

    async def get_messages(
        self,
        *,
        max_chars: int | None = None,
    ) -> list[AgentMessage]:
        """Return messages ordered chronologically (oldest first).

        If max_chars is set, the most recent messages that fit within the
        character budget are kept (oldest messages are dropped first).
        """
        result = await self._db.execute(
            select(AgentMessage)
            .where(
                AgentMessage.session_id == self._session_id,
                AgentMessage.tenant_id == self._tenant_id,
            )
            .order_by(AgentMessage.created_at.asc())
        )
        messages = list(result.scalars().all())

        if max_chars is None:
            return messages

        total = 0
        kept: list[AgentMessage] = []
        for msg in reversed(messages):
            total += len(msg.content)
            if total > max_chars:
                break
            kept.insert(0, msg)
        return kept

    async def to_llm_messages(
        self,
        *,
        max_chars: int | None = None,
    ) -> list[dict[str, str]]:
        """Return messages in Ollama chat API format.

        Tool messages are emitted as "user" role so the LLM sees them as
        observations, consistent with the ReAct prompt protocol.
        """
        msgs = await self.get_messages(max_chars=max_chars)
        result: list[dict[str, str]] = []
        for msg in msgs:
            role = "user" if msg.role == "tool" else msg.role
            result.append({"role": role, "content": msg.content})
        return result
