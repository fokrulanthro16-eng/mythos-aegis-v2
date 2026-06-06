"""Agent runtime — single-turn ReAct loop (think → tool → observe → repeat).

Protocol:
  LLM outputs either:
    ACTION: {"tool": "<name>", "params": {...}}   → execute tool, feed result back
    ANSWER: <text>                                 → final answer, stop loop

Security: tool call params are never logged (only tool name + success flag).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import AgentLLMClient
from app.agent.prompt_builder import format_tool_result
from app.agent.schemas import ToolCallRecord
from app.agent.tools.registry import ToolRegistry
from app.core.exceptions import AIProviderUnavailableError
from app.core.security_context import SecurityContext

logger = logging.getLogger(__name__)

# Patterns are intentionally lenient to handle small-model formatting variance.
# ACTION pattern: non-greedy JSON capture, one per line
_ACTION_RE = re.compile(
    r"ACTION:\s*(\{.*?\})\s*$", re.MULTILINE | re.DOTALL | re.IGNORECASE
)
# ANSWER pattern: without DOTALL so '.' stops at newline; this prevents
# over-capture when ACTION: appears on a later line.
_ANSWER_RE = re.compile(r"ANSWER:\s*(.*)", re.IGNORECASE)


@dataclass
class TurnResult:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    iterations: int = 0


class AgentRuntime:
    """Single-turn agent loop over the ReAct ACTION/ANSWER protocol."""

    def __init__(
        self,
        registry: ToolRegistry,
        llm: AgentLLMClient | None = None,
    ) -> None:
        self._registry = registry
        self._llm = llm or AgentLLMClient()

    # ── Response parsing ──────────────────────────────────────────────────────

    def _parse_response(self, text: str) -> tuple[str | None, dict[str, Any] | None]:
        """Return (final_answer | None, tool_call_dict | None)."""
        action_m = _ACTION_RE.search(text)
        answer_m = _ANSWER_RE.search(text)

        # ACTION before ANSWER (or no ANSWER) → prefer executing the tool
        if action_m and (not answer_m or action_m.start() < answer_m.start()):
            try:
                call: dict[str, Any] = json.loads(action_m.group(1))
                if isinstance(call, dict) and "tool" in call:
                    return None, call
            except (json.JSONDecodeError, ValueError):
                logger.debug("agent.runtime: malformed ACTION JSON")

        if answer_m:
            return answer_m.group(1).strip(), None

        # Fallback: treat the whole response as the answer
        return text.strip(), None

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run_turn(
        self,
        initial_messages: list[dict[str, str]],
        ctx: SecurityContext,
        db_session: AsyncSession,
        max_iterations: int = 5,
    ) -> TurnResult:
        """Run the agent loop for one user turn.

        initial_messages = [system_prompt, *history, user_question]
        """
        messages = list(initial_messages)
        tool_calls: list[ToolCallRecord] = []

        for iteration in range(max_iterations):
            try:
                response = await self._llm.chat(messages, max_tokens=512)
            except AIProviderUnavailableError as exc:
                return TurnResult(
                    answer=f"AI provider unavailable: {exc.message}",
                    tool_calls=tool_calls,
                    iterations=iteration,
                )

            final_answer, tool_call = self._parse_response(response)

            if final_answer is not None:
                logger.debug(
                    "agent.runtime: answered iteration=%d answer_chars=%d",
                    iteration + 1,
                    len(final_answer),
                )
                return TurnResult(
                    answer=final_answer,
                    tool_calls=tool_calls,
                    iterations=iteration + 1,
                )

            if tool_call is not None:
                tool_name: str = str(tool_call.get("tool", ""))
                params: dict[str, Any] = tool_call.get("params", {})
                if not isinstance(params, dict):
                    params = {}

                messages.append({"role": "assistant", "content": response})

                tool = self._registry.get(tool_name)
                if tool is None:
                    err = f"Unknown tool: {tool_name!r}"
                    record = ToolCallRecord(
                        tool_name=tool_name, params=params, success=False, error=err
                    )
                    tool_result_str = format_tool_result(tool_name, False, None, err)
                else:
                    try:
                        result = await tool.execute(params, ctx, db_session)
                    except Exception:  # noqa: BLE001
                        logger.exception("agent.runtime: tool_error tool=%s", tool_name)
                        record = ToolCallRecord(
                            tool_name=tool_name,
                            params=params,
                            success=False,
                            error="Tool execution error",
                        )
                        tool_result_str = format_tool_result(
                            tool_name, False, None, "Tool execution error"
                        )
                    else:
                        record = ToolCallRecord(
                            tool_name=tool_name,
                            params=params,
                            success=result.success,
                            error=result.error,
                        )
                        tool_result_str = format_tool_result(
                            tool_name, result.success, result.data, result.error
                        )

                tool_calls.append(record)
                messages.append({"role": "user", "content": tool_result_str})
                logger.debug(
                    "agent.runtime: tool=%s success=%s iteration=%d",
                    tool_name,
                    record.success,
                    iteration + 1,
                )
                continue

            # Neither ACTION nor ANSWER — treat as final answer
            return TurnResult(
                answer=response.strip(),
                tool_calls=tool_calls,
                iterations=iteration + 1,
            )

        # Max iterations reached — force a final answer
        messages.append(
            {
                "role": "user",
                "content": (
                    "You have reached the tool call limit. Provide your ANSWER: now."
                ),
            }
        )
        try:
            response = await self._llm.chat(messages, max_tokens=512)
        except AIProviderUnavailableError:
            response = "Unable to generate a final answer."

        final_answer, _ = self._parse_response(response)
        return TurnResult(
            answer=final_answer or response.strip(),
            tool_calls=tool_calls,
            iterations=max_iterations,
        )
