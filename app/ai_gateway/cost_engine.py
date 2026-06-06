"""Cost estimation for AI gateway providers.

Ollama runs locally — cost is always $0.00.
Cloud provider rates live here so the service layer stays cost-aware when
additional backends are added.
"""

from __future__ import annotations

# Cost table in USD per 1 000 tokens.
# Ollama = $0 (local inference; no per-token billing).
_COST_PER_1K: dict[str, dict[str, float]] = {
    "ollama": {
        "input": 0.0,
        "output": 0.0,
    },
    # Placeholder entries for future cloud providers:
    # "openai-gpt4o": {"input": 0.005, "output": 0.015},
    # "claude-sonnet": {"input": 0.003, "output": 0.015},
}

_ZERO_RATE: dict[str, float] = {"input": 0.0, "output": 0.0}


def estimate_tokens(text: str) -> int:
    """Rough token count using the 4-chars-per-token heuristic.

    Returns at least 1 so callers never receive zero token counts.
    """
    return max(1, len(text) // 4)


def calculate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    """Return the estimated USD cost for the given token counts.

    Unknown providers fall back to $0.00 (fail-safe; never raises).
    """
    rates = _COST_PER_1K.get(provider.lower(), _ZERO_RATE)
    raw = (
        input_tokens / 1_000.0 * rates["input"]
        + output_tokens / 1_000.0 * rates["output"]
    )
    return round(raw, 8)
