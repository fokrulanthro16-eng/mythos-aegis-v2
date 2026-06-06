"""System prompt construction for the agent runtime.

The system prompt lists all registered tools in a format qwen2.5:1.5b can
reliably follow: ACTION: <JSON> for tool calls, ANSWER: <text> for final answers.
"""

from __future__ import annotations

import json

from app.agent.tools.registry import ToolRegistry

_SYSTEM_TEMPLATE = """\
You are a helpful AI agent for the Mythos Aegis enterprise platform.

You have access to the following tools:

{tools_json}

HOW TO USE TOOLS:
To call a tool, output exactly this format on its own line:
ACTION: {{"tool": "tool_name", "params": {{"param1": "value1"}}}}

To give your final answer:
ANSWER: <your complete answer here>

RULES:
- If you do not need a tool, respond with ANSWER: immediately
- Call only one tool per response
- After seeing a tool result, either call another tool or give your ANSWER:
- Never invent tool results
- Be concise
"""

_TOOL_RESULT_TEMPLATE = "TOOL_RESULT [{tool_name}]: {result}"


def build_system_prompt(registry: ToolRegistry) -> str:
    """Build the agent system prompt with all registered tool definitions."""
    definitions = registry.list_definitions()
    tools_json = json.dumps([d.to_dict() for d in definitions], indent=2)
    return _SYSTEM_TEMPLATE.format(tools_json=tools_json)


def format_tool_result(
    tool_name: str,
    success: bool,
    data: object,
    error: str | None,
) -> str:
    """Format a tool result as a user message for the chat API."""
    if success:
        result_str = json.dumps(data, default=str)
    else:
        result_str = json.dumps({"error": error or "unknown error"})
    return _TOOL_RESULT_TEMPLATE.format(tool_name=tool_name, result=result_str)
