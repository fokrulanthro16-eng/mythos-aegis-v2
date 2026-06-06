"""Unit tests for the agent runtime and prompt builder."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agent.prompt_builder import build_system_prompt, format_tool_result
from app.agent.runtime import AgentRuntime
from app.agent.tools.base import ToolDefinition, ToolResult
from app.agent.tools.registry import ToolRegistry
from app.core.security_context import SecurityContext


def _ctx() -> SecurityContext:
    return SecurityContext(
        request_id=uuid4(),
        current_user_id=uuid4(),
        tenant_id=uuid4(),
        roles=frozenset({"user"}),
        permissions=frozenset({"agent.run", "rag.search"}),
    )


def _session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    return s


def _empty_registry() -> ToolRegistry:
    return ToolRegistry()


# ── AgentRuntime._parse_response ─────────────────────────────────────────────


class TestParseResponse:
    def setup_method(self) -> None:
        self.runtime = AgentRuntime(_empty_registry())

    def test_detects_answer(self) -> None:
        answer, tool_call = self.runtime._parse_response("ANSWER: hello world")
        assert answer == "hello world"
        assert tool_call is None

    def test_detects_action(self) -> None:
        action = '{"tool":"rag_search","params":{"query":"test","project_id":"x"}}'
        text = f"ACTION: {action}"
        answer, tool_call = self.runtime._parse_response(text)
        assert answer is None
        assert tool_call is not None
        assert tool_call["tool"] == "rag_search"

    def test_action_before_answer_prefers_action(self) -> None:
        text = 'ACTION: {"tool": "rag_search", "params": {}}\nANSWER: fallback'
        _, tool_call = self.runtime._parse_response(text)
        assert tool_call is not None

    def test_answer_before_action_prefers_answer(self) -> None:
        text = 'ANSWER: my answer\nACTION: {"tool": "rag_search", "params": {}}'
        answer, _ = self.runtime._parse_response(text)
        assert answer == "my answer"

    def test_malformed_json_falls_back_to_answer(self) -> None:
        text = "ACTION: {not valid json}\nANSWER: fallback answer"
        answer, tool_call = self.runtime._parse_response(text)
        assert answer == "fallback answer"
        assert tool_call is None

    def test_no_markers_returns_whole_response(self) -> None:
        text = "Just a plain response with no markers."
        answer, tool_call = self.runtime._parse_response(text)
        assert answer == text.strip()
        assert tool_call is None

    def test_multiline_answer(self) -> None:
        # Without re.DOTALL, the regex stops at the first newline.
        # This prevents over-capture when ACTION: appears on a later line.
        text = "ANSWER: first line\nsecond line\nthird line"
        answer, _ = self.runtime._parse_response(text)
        assert answer is not None
        assert "first line" in answer


# ── AgentRuntime.run_turn ────────────────────────────────────────────────────


class TestRunTurn:
    @pytest.mark.asyncio
    async def test_direct_answer_no_tool_calls(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="ANSWER: The answer is 42.")

        runtime = AgentRuntime(_empty_registry(), llm=mock_llm)
        result = await runtime.run_turn(
            [{"role": "user", "content": "What is the answer?"}],
            _ctx(),
            _session(),
        )

        assert result.answer == "The answer is 42."
        assert result.tool_calls == []
        assert result.iterations == 1

    @pytest.mark.asyncio
    async def test_tool_call_then_answer(self) -> None:
        # Mock tool
        mock_tool = MagicMock()
        mock_tool.definition = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[],
        )
        mock_tool.execute = AsyncMock(
            return_value=ToolResult(success=True, data={"result": "42"})
        )

        registry = ToolRegistry()
        registry.register(mock_tool)

        responses = [
            'ACTION: {"tool": "test_tool", "params": {}}',
            "ANSWER: The result is 42.",
        ]
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=responses)

        runtime = AgentRuntime(registry, llm=mock_llm)
        result = await runtime.run_turn(
            [{"role": "user", "content": "What is the result?"}],
            _ctx(),
            _session(),
        )

        assert result.answer == "The result is 42."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "test_tool"
        assert result.tool_calls[0].success is True
        assert result.iterations == 2

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_record(self) -> None:
        responses = [
            'ACTION: {"tool": "nonexistent", "params": {}}',
            "ANSWER: Could not find it.",
        ]
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=responses)

        runtime = AgentRuntime(_empty_registry(), llm=mock_llm)
        result = await runtime.run_turn(
            [{"role": "user", "content": "test"}],
            _ctx(),
            _session(),
        )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].success is False
        assert "Unknown tool" in (result.tool_calls[0].error or "")

    @pytest.mark.asyncio
    async def test_max_iterations_forces_answer(self) -> None:
        mock_tool = MagicMock()
        mock_tool.definition = ToolDefinition(
            name="loop_tool", description="loops", parameters=[]
        )
        mock_tool.execute = AsyncMock(
            return_value=ToolResult(success=True, data={"x": 1})
        )

        registry = ToolRegistry()
        registry.register(mock_tool)

        mock_llm = AsyncMock()
        # Always returns a tool call — never terminates naturally
        mock_llm.chat = AsyncMock(
            return_value='ACTION: {"tool": "loop_tool", "params": {}}'
        )

        runtime = AgentRuntime(registry, llm=mock_llm)
        result = await runtime.run_turn(
            [{"role": "user", "content": "loop"}],
            _ctx(),
            _session(),
            max_iterations=2,
        )

        # After max_iterations, one more LLM call is made to force answer
        # Total calls = 2 (iterations) + 1 (forced answer) = 3
        assert mock_llm.chat.call_count == 3
        assert result.iterations == 2

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_error_answer(self) -> None:
        from app.core.exceptions import AIProviderUnavailableError

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(
            side_effect=AIProviderUnavailableError("Ollama offline")
        )

        runtime = AgentRuntime(_empty_registry(), llm=mock_llm)
        result = await runtime.run_turn(
            [{"role": "user", "content": "help"}],
            _ctx(),
            _session(),
        )

        assert "unavailable" in result.answer.lower()
        assert result.iterations == 0


# ── Prompt builder ────────────────────────────────────────────────────────────


class TestPromptBuilder:
    def test_build_system_prompt_contains_tool_names(self) -> None:
        registry = ToolRegistry.default()
        prompt = build_system_prompt(registry)
        assert "rag_search" in prompt
        assert "tenant_lookup" in prompt
        assert "sql_query" in prompt
        assert "rbac_check" in prompt
        assert "audit_log" in prompt

    def test_build_system_prompt_contains_action_format(self) -> None:
        prompt = build_system_prompt(ToolRegistry())
        assert "ACTION:" in prompt
        assert "ANSWER:" in prompt

    def test_format_tool_result_success(self) -> None:
        msg = format_tool_result("rag_search", True, {"count": 2}, None)
        assert "TOOL_RESULT" in msg
        assert "rag_search" in msg
        assert "count" in msg

    def test_format_tool_result_failure(self) -> None:
        msg = format_tool_result("rag_search", False, None, "Embedding failed")
        assert "error" in msg.lower()
        assert "Embedding failed" in msg
