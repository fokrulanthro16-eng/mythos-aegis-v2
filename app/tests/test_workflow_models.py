"""Unit tests for workflow Pydantic domain models and template engine."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.workflow.models import (
    RetryConfig,
    StepDefinition,
    StepType,
    WorkflowDefinitionModel,
)
from app.workflow.templates import resolve, resolve_dict

# ── RetryConfig ───────────────────────────────────────────────────────────────


class TestRetryConfig:
    def test_defaults(self) -> None:
        rc = RetryConfig()
        assert rc.max_attempts == 3
        assert rc.initial_delay_seconds == 1.0
        assert rc.backoff_multiplier == 2.0
        assert rc.max_delay_seconds == 60.0

    def test_custom_values(self) -> None:
        rc = RetryConfig(max_attempts=5, initial_delay_seconds=0.5)
        assert rc.max_attempts == 5
        assert rc.initial_delay_seconds == 0.5

    def test_max_attempts_bounds(self) -> None:
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=0)
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=11)


# ── StepDefinition ────────────────────────────────────────────────────────────


class TestStepDefinition:
    def test_valid_step(self) -> None:
        step = StepDefinition(
            id="extract_text",
            name="Extract Text",
            type=StepType.VISION_EXTRACT,
        )
        assert step.id == "extract_text"
        assert step.type == StepType.VISION_EXTRACT
        assert step.depends_on == []
        assert step.config == {}

    def test_id_rejects_uppercase(self) -> None:
        with pytest.raises(ValidationError):
            StepDefinition(id="Extract", name="n", type=StepType.TRANSFORM)

    def test_id_rejects_spaces(self) -> None:
        with pytest.raises(ValidationError):
            StepDefinition(id="my step", name="n", type=StepType.TRANSFORM)

    def test_id_allows_hyphens_underscores(self) -> None:
        step = StepDefinition(id="my-step_01", name="ok", type=StepType.TRANSFORM)
        assert step.id == "my-step_01"

    def test_all_step_types_valid(self) -> None:
        for stype in StepType:
            step = StepDefinition(id="s", name="n", type=stype)
            assert step.type == stype

    def test_depends_on_stored(self) -> None:
        step = StepDefinition(
            id="b", name="B", type=StepType.AGENT_TASK, depends_on=["a"]
        )
        assert step.depends_on == ["a"]


# ── WorkflowDefinitionModel ───────────────────────────────────────────────────


def _make_step(step_id: str, deps: list[str] | None = None) -> dict:
    return {
        "id": step_id,
        "name": step_id.title(),
        "type": "transform",
        "depends_on": deps or [],
    }


class TestWorkflowDefinitionModel:
    def test_valid_single_step(self) -> None:
        wf = WorkflowDefinitionModel(
            name="My Workflow",
            steps=[_make_step("step1")],
        )
        assert wf.name == "My Workflow"
        assert len(wf.steps) == 1

    def test_valid_multi_step_with_deps(self) -> None:
        wf = WorkflowDefinitionModel(
            name="Pipeline",
            steps=[_make_step("a"), _make_step("b", ["a"])],
        )
        assert wf.steps[1].depends_on == ["a"]

    def test_rejects_duplicate_step_ids(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            WorkflowDefinitionModel(
                name="Bad",
                steps=[_make_step("dup"), _make_step("dup")],
            )

    def test_rejects_unknown_dependency(self) -> None:
        with pytest.raises(ValidationError, match="unknown step"):
            WorkflowDefinitionModel(
                name="Bad",
                steps=[_make_step("a", ["nonexistent"])],
            )

    def test_empty_steps_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowDefinitionModel(name="Empty", steps=[])

    def test_description_defaults_empty(self) -> None:
        wf = WorkflowDefinitionModel(name="W", steps=[_make_step("s")])
        assert wf.description == ""


# ── Template engine ───────────────────────────────────────────────────────────


class TestResolve:
    def test_resolves_input_field(self) -> None:
        ctx = {"input": {"filename": "invoice.pdf"}, "steps": {}}
        assert resolve("{{ input.filename }}", ctx) == "invoice.pdf"

    def test_resolves_step_output(self) -> None:
        ctx = {
            "input": {},
            "steps": {"extract": {"output": {"text": "Hello world"}}},
        }
        assert resolve("{{ steps.extract.output.text }}", ctx) == "Hello world"

    def test_missing_path_returns_empty(self) -> None:
        ctx = {"input": {}, "steps": {}}
        assert resolve("{{ input.missing }}", ctx) == ""

    def test_no_template_unchanged(self) -> None:
        ctx = {"input": {}, "steps": {}}
        assert resolve("plain text", ctx) == "plain text"

    def test_mixed_template(self) -> None:
        ctx = {"input": {"name": "Acme"}, "steps": {}}
        assert resolve("Hello {{ input.name }}!", ctx) == "Hello Acme!"

    def test_multiple_placeholders(self) -> None:
        ctx = {"input": {"a": "X", "b": "Y"}, "steps": {}}
        result = resolve("{{ input.a }} and {{ input.b }}", ctx)
        assert result == "X and Y"


class TestResolveDict:
    def test_resolves_string_values(self) -> None:
        ctx = {"input": {"q": "hello"}, "steps": {}}
        config = {"query": "{{ input.q }}", "top_k": 5}
        result = resolve_dict(config, ctx)
        assert result["query"] == "hello"
        assert result["top_k"] == 5

    def test_resolves_nested_dict(self) -> None:
        ctx = {"input": {"val": "42"}, "steps": {}}
        config = {"outer": {"inner": "{{ input.val }}"}}
        result = resolve_dict(config, ctx)
        assert result["outer"]["inner"] == "42"

    def test_resolves_list_strings(self) -> None:
        ctx = {"input": {"tag": "foo"}, "steps": {}}
        config = {"tags": ["{{ input.tag }}", "static"]}
        result = resolve_dict(config, ctx)
        assert result["tags"] == ["foo", "static"]

    def test_non_string_values_preserved(self) -> None:
        ctx = {"input": {}, "steps": {}}
        config = {"count": 10, "flag": True, "ratio": 0.5}
        result = resolve_dict(config, ctx)
        assert result == config
