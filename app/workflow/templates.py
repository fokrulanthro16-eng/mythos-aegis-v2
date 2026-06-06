"""Template variable resolution for workflow step configs.

Syntax: ``{{ path.to.value }}`` where the path navigates a nested dict.

Context structure::

    {
        "input":  { ...workflow execution input... },
        "steps":  { "step_id": { "output": {...}, "status": "completed" } },
    }

Any unresolved reference silently resolves to an empty string.
"""

from __future__ import annotations

import re
from typing import Any

_TEMPLATE_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def resolve(template: str, context: dict[str, Any]) -> str:
    """Replace ``{{ path }}`` placeholders with values from *context*."""

    def _replace(match: re.Match[str]) -> str:
        path = match.group(1).strip()
        value: Any = context
        for part in path.split("."):
            if isinstance(value, dict):
                value = value.get(part, "")
            else:
                value = ""
                break
        return str(value) if value is not None else ""

    return _TEMPLATE_RE.sub(_replace, template)


def resolve_dict(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Recursively resolve templates in all string values of *config*."""
    result: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, str):
            result[key] = resolve(value, context)
        elif isinstance(value, dict):
            result[key] = resolve_dict(value, context)
        elif isinstance(value, list):
            result[key] = [
                resolve(v, context) if isinstance(v, str) else v for v in value
            ]
        else:
            result[key] = value
    return result
