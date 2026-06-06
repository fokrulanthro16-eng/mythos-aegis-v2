"""Unit tests for the conversation memory service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agent.memory import ConversationMemory
from app.db.models.agent_message import AgentMessage


def _make_message(role: str, content: str) -> AgentMessage:
    msg = MagicMock(spec=AgentMessage)
    msg.id = uuid4()
    msg.role = role
    msg.content = content
    msg.tool_name = None
    return msg


def _session_returning(messages: list[AgentMessage]) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = messages

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session.execute = AsyncMock(return_value=result_mock)
    return session


class TestConversationMemory:
    @pytest.mark.asyncio
    async def test_add_message_persists_to_db(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        memory = ConversationMemory(session, uuid4(), uuid4())
        msg = await memory.add_message("user", "Hello agent")

        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert msg.role == "user"
        assert msg.content == "Hello agent"

    @pytest.mark.asyncio
    async def test_get_messages_returns_all(self) -> None:
        msgs = [
            _make_message("user", "Hi"),
            _make_message("assistant", "Hello!"),
        ]
        session = _session_returning(msgs)
        memory = ConversationMemory(session, uuid4(), uuid4())
        result = await memory.get_messages()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_messages_windowing_drops_oldest(self) -> None:
        # 3 msgs × 100 chars, budget=150 → keep last 1 (100≤150, two would be 200>150)
        msgs = [
            _make_message("user", "a" * 100),
            _make_message("assistant", "b" * 100),
            _make_message("user", "c" * 100),
        ]
        session = _session_returning(msgs)
        memory = ConversationMemory(session, uuid4(), uuid4())
        result = await memory.get_messages(max_chars=150)
        # Should keep the last 1 message (100 ≤ 150; adding second would be 200 > 150)
        assert len(result) == 1
        assert result[0].content == "c" * 100

    @pytest.mark.asyncio
    async def test_get_messages_no_limit_returns_all(self) -> None:
        msgs = [_make_message("user", "x" * 5000) for _ in range(10)]
        session = _session_returning(msgs)
        memory = ConversationMemory(session, uuid4(), uuid4())
        result = await memory.get_messages()
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_to_llm_messages_converts_tool_to_user(self) -> None:
        msgs = [
            _make_message("user", "Ask"),
            _make_message("assistant", "ACTION: ..."),
            _make_message("tool", "TOOL_RESULT [rag_search]: {...}"),
            _make_message("assistant", "ANSWER: done"),
        ]
        session = _session_returning(msgs)
        memory = ConversationMemory(session, uuid4(), uuid4())
        llm_msgs = await memory.to_llm_messages()

        assert llm_msgs[0]["role"] == "user"
        assert llm_msgs[1]["role"] == "assistant"
        assert llm_msgs[2]["role"] == "user"  # tool → user
        assert llm_msgs[3]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_add_message_with_tool_fields(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        memory = ConversationMemory(session, uuid4(), uuid4())
        msg = await memory.add_message(
            "tool",
            "TOOL_RESULT [rag_search]: {}",
            tool_name="rag_search",
            tool_input={"query": "test"},
            tool_output={"success": True},
        )

        assert msg.tool_name == "rag_search"
        assert msg.tool_input is not None
        assert '"query"' in msg.tool_input
