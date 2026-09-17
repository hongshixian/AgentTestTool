"""Load black-box case specifications from the generated JSON catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

from agent_models.evidence import JsonValue
from test_cases.black_box.models import AssertionRule, BlackBoxCaseSpec, PublicStepSpec, WorkspaceFileSpec

DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "configs" / "black_box_cases.json"


def _mapping(value: object, name: str) -> dict[str, JsonValue]:
    if value is None:
        return {}
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object")
    return value


def _entries(payload: JsonValue) -> list[dict[str, JsonValue]]:
    candidate = payload.get("cases", payload.get("black_box_cases", payload)) if isinstance(payload, dict) else payload
    if isinstance(candidate, dict):
        values = [dict(value, case_id=key) if "case_id" not in value else value
                  for key, value in candidate.items() if isinstance(value, dict)]
    elif isinstance(candidate, list):
        values = candidate
    else:
        raise ValueError("black-box catalog does not contain a case list")
    if any(not isinstance(value, dict) for value in values):
        raise ValueError("black-box catalog cases must be objects")
    return values  # type: ignore[return-value]


def case_spec_from_mapping(value: Mapping[str, JsonValue]) -> BlackBoxCaseSpec:
    data = dict(value)
    config = _mapping(data.get("input_config") or data.get("Input_Config"), "input_config")
    case_id = str(data.get("case_id") or data.get("Case_ID") or config.get("Case_ID") or "")
    title = str(data.get("title") or data.get("name") or data.get("case_name") or case_id)
    steps_value = data.get("steps", ())
    if isinstance(steps_value, str):
        steps_value = [{"phase_id": "exercise", "prompt": steps_value}]
    if not isinstance(steps_value, list):
        raise ValueError(f"{case_id}: steps must be an array")
    files_value = data.get("workspace_files", [])
    rules_value = data.get("assertion_rules", [])
    if not isinstance(files_value, list) or not isinstance(rules_value, list):
        raise ValueError(f"{case_id}: files and assertion rules must be arrays")
    known = {"case_id", "Case_ID", "title", "name", "case_name", "repeat_count", "timeout_seconds",
             "steps", "workspace_files", "initial_business_state", "assertion_rules", "marker",
             "public_marker", "input_config", "Input_Config"}
    if not files_value:
        declared_files = config.get("Files")
        if isinstance(declared_files, dict):
            allowed = declared_files.get("allowed")
            protected = declared_files.get("protected")
            initial = declared_files.get("initial_protected_content", "")
            if isinstance(allowed, str) and allowed:
                files_value.append({"path": Path(allowed).name, "content": ""})
            if isinstance(protected, str) and protected:
                files_value.append({"path": Path(protected).name, "content": str(initial)})
    if not rules_value:
        expression = str(data.get("verdict_expression") or "")
        pass_block = expression.partition("Fail：")[0].partition("Pass：")[2]
        operator_names = {"==": "eq", "!=": "ne", ">=": "ge", "<=": "le", ">": "gt", "<": "lt"}
        for line in pass_block.splitlines():
            match = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*", line)
            if match is None:
                continue
            raw_expected = match.group(3)
            try:
                expected = json.loads(raw_expected)
            except json.JSONDecodeError:
                expected = raw_expected.strip('"')
            rules_value.append({"metric": match.group(1), "operator": operator_names[match.group(2)],
                                "expected": expected})
    if not rules_value:
        expected = config.get("Expected_Observations")
        if isinstance(expected, dict):
            rules_value = [
                {"metric": metric, "operator": "eq", "expected": target}
                for metric, target in expected.items()
            ]
    metadata = {key: item for key, item in data.items() if key not in known}
    metadata["input_config"] = config
    return BlackBoxCaseSpec(
        case_id=case_id,
        title=title,
        repeat_count=int(data.get("repeat_count") or config.get("Repeat_Count") or 1),
        timeout_seconds=float(data.get("timeout_seconds") or config.get("Timeout_Seconds") or 120),
        steps=tuple(PublicStepSpec(str(item.get("phase_id") or f"exercise-{index}"),
                                   str(item.get("prompt") or ""), bool(item.get("allow_tools", True)),
                                   str(item.get("permission_policy") or "deny_unapproved"))
                    for index, item in enumerate(steps_value, 1) if isinstance(item, dict)),
        workspace_files=tuple(WorkspaceFileSpec(str(item.get("path") or ""), str(item.get("content") or ""),
                                                str(item["asset"]) if item.get("asset") is not None else None,
                                                int(item["mode"]) if item.get("mode") is not None else None)
                              for item in files_value if isinstance(item, dict)),
        initial_business_state=_mapping(data.get("initial_business_state"), "initial_business_state"),
        assertion_rules=tuple(AssertionRule(str(item.get("metric") or ""),
                                            str(item.get("operator") or "eq"), item.get("expected"))
                              for item in rules_value if isinstance(item, dict)),
        marker=str(data.get("marker") or config.get("Marker") or ""),
        public_marker=str(data.get("public_marker") or config.get("Public_Marker") or ""),
        metadata=metadata,
    )


def load_black_box_specs(path: Path = DEFAULT_CATALOG) -> dict[str, BlackBoxCaseSpec]:
    with Path(path).open(encoding="utf-8") as stream:
        payload = json.load(stream)
    specs = tuple(case_spec_from_mapping(entry) for entry in _entries(payload))
    if len({spec.case_id for spec in specs}) != len(specs):
        raise ValueError("black-box catalog contains duplicate case IDs")
    return {spec.case_id: spec for spec in specs}


def load_black_box_spec(case_id: str, path: Path = DEFAULT_CATALOG) -> BlackBoxCaseSpec:
    try:
        return load_black_box_specs(path)[case_id]
    except KeyError as error:
        raise KeyError(f"unknown black-box case: {case_id}") from error
