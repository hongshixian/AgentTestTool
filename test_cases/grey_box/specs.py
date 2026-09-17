"""Load generated grey-box specifications."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from agent_models.evidence import JsonValue


DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "configs" / "grey_box_cases.json"


@dataclass(frozen=True, slots=True)
class GreyBoxCaseSpec:
    case_id: str
    title: str
    evidence_scope: str
    repeat_count: int
    timeout_seconds: float
    steps: str
    verdict_expression: str
    required_evidence: str
    required_capabilities: str
    input_config: Mapping[str, JsonValue]


def load_grey_box_specs(path: Path = DEFAULT_CATALOG) -> dict[str, GreyBoxCaseSpec]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    result: dict[str, GreyBoxCaseSpec] = {}
    for item in payload["cases"]:
        config = dict(item["input_config"])
        spec = GreyBoxCaseSpec(
            case_id=str(item["case_id"]),
            title=str(item["title"]),
            evidence_scope=str(item["evidence_scope"]),
            repeat_count=int(config.get("Repeat_Count") or 1),
            timeout_seconds=float(config.get("Timeout_Seconds") or 180),
            steps=str(item["steps"]),
            verdict_expression=str(item["verdict_expression"]),
            required_evidence=str(item["required_evidence"]),
            required_capabilities=str(item["required_capabilities"]),
            input_config=MappingProxyType(config),
        )
        result[spec.case_id] = spec
    return result


def load_grey_box_spec(case_id: str, path: Path = DEFAULT_CATALOG) -> GreyBoxCaseSpec:
    try:
        return load_grey_box_specs(path)[case_id]
    except KeyError as error:
        raise KeyError(f"unknown grey-box case: {case_id}") from error
