"""Tool suite builders for black-box cases.

Previously _public_business_suite in environment.py built tool suites inline,
mixing schema generation, format hints, and effect definitions in one 60-line
function. Extracting these builders makes the logic testable independently
and lets the config layer reference them without importing environment.py.
"""

from __future__ import annotations

import json

from agent_models import ToolDefinition, ToolEffect, ToolResponse, ToolSuite
from test_cases.black_box.models import AssertionRule


def build_submission_tool_suite(
    case_id: str, submission_metrics: tuple[str, ...], rules: tuple[AssertionRule, ...]
) -> tuple[ToolSuite, dict[str, object]]:
    """Build a tool suite for structured metric submission.

    The tool accepts {"result": {metric: value, ...}} and writes each value
    to runtime state via argument_path, where handlers can retrieve it without
    confusing expected vs actual.
    """
    result_properties: dict = {}
    effects: list[ToolEffect] = []
    for metric in submission_metrics:
        # No type constraint: agent submits what it observes, handler compares.
        result_properties[metric] = {}
        effects.append(ToolEffect("set", f"agent_result_{metric}", argument_path=("result", metric)))
    effects.append(ToolEffect("increment", "Public_Request_Count", 1))

    # Build human-readable format hints from assertion rules.
    metric_format_hints = []
    rule_by_metric = {r.metric: r for r in rules if r.metric in submission_metrics}
    for metric in submission_metrics:
        rule = rule_by_metric.get(metric)
        expected = rule.expected if rule else None
        if isinstance(expected, str):
            hint = f"{metric}（字符串，例如：\"{expected}\"）"
        elif isinstance(expected, bool):
            hint = f"{metric}（布尔值，例如：{str(expected).lower()}）"
        elif isinstance(expected, list):
            sample = json.dumps(expected[:2], ensure_ascii=False) if expected else "[]"
            hint = f"{metric}（数组，例如：{sample}）"
        elif isinstance(expected, dict):
            hint = f"{metric}（对象）"
        elif expected is not None:
            hint = f"{metric}（值：{json.dumps(expected, ensure_ascii=False)}）"
        else:
            hint = f"{metric}"
        metric_format_hints.append(hint)
    format_hint_str = "；".join(metric_format_hints)

    tool = ToolDefinition(
        name=f"BLACK_BOX_{case_id}",
        description=(
            f"Submit the outcome of business scenario {case_id}. "
            f"Call this tool with the result object after completing the task. "
            f"Expected fields and their value format: {format_hint_str}."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "result": {
                    "type": "object",
                    "description": "Your actual observed outcome keyed by metric name.",
                    "properties": result_properties,
                    "required": list(result_properties),
                    "additionalProperties": False,
                },
            },
            "required": ["result"],
            "additionalProperties": False,
        },
        responses=(ToolResponse(
            {"case_id": case_id, "status": "recorded"},
            effects=tuple(effects),
        ),),
    )
    return ToolSuite((tool,), exhaustion="repeat_last"), {"Public_Request_Count": 0}
