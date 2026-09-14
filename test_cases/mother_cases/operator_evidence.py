"""Conclude mother cases that require evidence controlled by the operator."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from agent_models import AgentModel
from test_cases.mother_cases.base import MotherCaseScenarioRunner


_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_PATH = _ROOT / "configs" / "operator_evidence_cases.json"
_ALLOWED_EVIDENCE_TYPES = frozenset({"材料", "访谈", "服务端证据"})


@dataclass(frozen=True, slots=True)
class OperatorEvidenceRequirement:
    """Evidence that an independent CLI-only assessment cannot obtain."""

    source_case_id: str
    name: str
    evidence_types: tuple[str, ...]
    required_evidence: str


def _required_text(item: Mapping[str, Any], field: str) -> str:
    value = str(item.get(field) or "").strip()
    if not value:
        raise ValueError(f"运营方证据清单缺少 {field}")
    return value


@lru_cache(maxsize=1)
def operator_evidence_requirements() -> dict[str, OperatorEvidenceRequirement]:
    """Load and validate the checked-in operator evidence inventory."""

    payload = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if payload.get("case_count") != 63 or not isinstance(cases, list):
        raise ValueError("运营方证据清单必须恰好包含 63 条母用例")

    indexed: dict[str, OperatorEvidenceRequirement] = {}
    for item in cases:
        if not isinstance(item, Mapping):
            raise ValueError("运营方证据清单包含非对象条目")
        source_case_id = _required_text(item, "source_case_id")
        raw_types = item.get("evidence_types")
        if not isinstance(raw_types, list) or not raw_types:
            raise ValueError(f"{source_case_id} 缺少 evidence_types")
        evidence_types = tuple(str(value).strip() for value in raw_types)
        if any(value not in _ALLOWED_EVIDENCE_TYPES for value in evidence_types):
            raise ValueError(f"{source_case_id} 包含未知运营方证据类型")
        if source_case_id in indexed:
            raise ValueError(f"运营方证据清单 ID 重复：{source_case_id}")
        indexed[source_case_id] = OperatorEvidenceRequirement(
            source_case_id=source_case_id,
            name=_required_text(item, "name"),
            evidence_types=evidence_types,
            required_evidence=_required_text(item, "required_evidence"),
        )
    if len(indexed) != 63:
        raise ValueError("运营方证据清单 ID 必须恰好有 63 个")
    return indexed


def operator_evidence_requirement(source_case_id: str) -> OperatorEvidenceRequirement:
    """Return one operator-controlled evidence requirement by mother-case ID."""

    try:
        return operator_evidence_requirements()[source_case_id]
    except KeyError as error:
        raise ValueError(f"{source_case_id} 未标记为需运营方举证") from error


class OperatorEvidenceMotherCaseRunner(MotherCaseScenarioRunner):
    """Return N/A without contacting the Agent when operator evidence is required."""

    def run_operator_evidence_case(
        self,
        *,
        source_case_id: str,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        requirement = operator_evidence_requirement(source_case_id)
        agent_model.environment.ledger.record(
            "pytest",
            "operator_evidence_required",
            {
                "source_case_id": requirement.source_case_id,
                "evidence_types": list(requirement.evidence_types),
                "required_evidence": requirement.required_evidence,
            },
        )
        evidence_label = "/".join(requirement.evidence_types)
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "需运营方材料/访谈/服务端证据："
                f"需运营方提供{evidence_label}；"
                f"{requirement.required_evidence}。"
                "本地 CLI 不执行代表路径。"
            ),
        )
