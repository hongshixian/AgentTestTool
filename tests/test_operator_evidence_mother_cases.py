"""Verify mother cases that require operator-controlled evidence."""

from __future__ import annotations

import ast
import importlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.mother_cases.operator_evidence import (
    OperatorEvidenceMotherCaseRunner,
    operator_evidence_requirement,
    operator_evidence_requirements,
)


ROOT = Path(__file__).resolve().parents[1]
OPERATOR_MANIFEST = ROOT / "configs" / "operator_evidence_cases.json"
MOTHER_MANIFEST = ROOT / "configs" / "mother_cases_v3.json"
CONCLUSION_MATERIAL = ROOT / "docs" / "operator_evidence_mother_cases.md"
FIXED_MARKER = "需运营方材料/访谈/服务端证据"


class _Ledger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, object]]] = []

    def record(self, source: str, kind: str, data: dict[str, object]) -> None:
        self.events.append((source, kind, data))


class _Model:
    def __init__(self) -> None:
        self.environment = SimpleNamespace(ledger=_Ledger())

    def check_authentication(self) -> None:
        raise AssertionError("operator-evidence cases must not authenticate")

    def send_prompt(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("operator-evidence cases must not send prompts")

    def configure_mock_tool(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("operator-evidence cases must not configure mock tools")

    def configure_mock_tools(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("operator-evidence cases must not configure mock tools")

    def start_session(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("operator-evidence cases must not start sessions")


def _payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _script_path(source_case_id: str) -> Path:
    stem = source_case_id.lower().replace("-", "_").replace(".", "_")
    return ROOT / "test_cases" / "mother_cases" / f"test_{stem}.py"


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def test_inventory_has_expected_counts_and_unique_ids() -> None:
    payload = _payload(OPERATOR_MANIFEST)
    cases = payload["cases"]

    assert isinstance(cases, list)
    assert payload["case_count"] == len(cases) == 63
    assert len({case["source_case_id"] for case in cases}) == 63

    classification = payload["classification"]
    assert classification == {
        "scope": "385条CLI宽松判定版v3母用例",
        "criterion": "第三方仅依赖本地CLI、普通测试账号和公开接口时，无法独立取得完整判定依据。",
        "interview_case_count": 44,
        "material_case_count": 15,
        "server_evidence_case_count": 6,
        "deduplicated_case_count": 63,
    }
    assert sum("访谈" in case["evidence_types"] for case in cases) == 44
    assert sum("材料" in case["evidence_types"] for case in cases) == 15
    assert sum("服务端证据" in case["evidence_types"] for case in cases) == 6


def test_inventory_matches_frozen_mother_case_names() -> None:
    operator_cases = _payload(OPERATOR_MANIFEST)["cases"]
    mother_cases = _payload(MOTHER_MANIFEST)["cases"]
    indexed = {case["source_case_id"]: case for case in mother_cases}

    assert len(mother_cases) == 385
    for case in operator_cases:
        source_case_id = case["source_case_id"]
        assert source_case_id in indexed
        assert case["name"] == indexed[source_case_id]["name"]
        assert case["classification_basis"] == {
            "priority": indexed[source_case_id]["priority"],
            "category": indexed[source_case_id]["category"],
            "arrangement": indexed[source_case_id]["arrangement"],
        }


def test_conclusion_material_covers_every_inventory_case() -> None:
    material = CONCLUSION_MATERIAL.read_text(encoding="utf-8")
    cases = _payload(OPERATOR_MANIFEST)["cases"]

    assert "共有 **63 条**" in material
    assert "占 **16.36%**" in material
    for case in cases:
        assert f"`{case['source_case_id']}`" in material
        assert case["required_evidence"] in material


def test_wrappers_only_delegate_to_operator_evidence_runner() -> None:
    cases = _payload(OPERATOR_MANIFEST)["cases"]

    for case in cases:
        source_case_id = case["source_case_id"]
        requirement = case["required_evidence"]
        path = _script_path(source_case_id)
        assert path.is_file(), source_case_id

        module = importlib.import_module(_module_name(path))
        assert module.OPERATOR_EVIDENCE_REQUIRED is True
        assert module.OPERATOR_EVIDENCE_REQUIREMENT == requirement

        classes = [
            value
            for value in vars(module).values()
            if inspect.isclass(value)
            and value.__module__ == module.__name__
            and issubclass(value, OperatorEvidenceMotherCaseRunner)
        ]
        assert len(classes) == 1, source_case_id
        class_doc = inspect.getdoc(classes[0])
        assert class_doc is not None
        assert FIXED_MARKER in class_doc
        assert "".join(requirement.split()) in "".join(class_doc.split())

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        test_methods = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        assert len(test_methods) == 1, source_case_id
        calls = [node for node in ast.walk(test_methods[0]) if isinstance(node, ast.Call)]
        assert len(calls) == 1, source_case_id
        assert isinstance(calls[0].func, ast.Attribute)
        assert calls[0].func.attr == "run_operator_evidence_case", source_case_id


def test_runner_concludes_not_applicable_without_agent_interaction() -> None:
    requirement = operator_evidence_requirements()["TC-5.5b-D3-01"]
    model = _Model()
    request = SimpleNamespace(node=SimpleNamespace(user_properties=[]))

    with pytest.raises(AssessmentOutcomeSignal) as outcome:
        OperatorEvidenceMotherCaseRunner().run_operator_evidence_case(
            source_case_id=requirement.source_case_id,
            agent_model=model,  # type: ignore[arg-type]
            request=request,  # type: ignore[arg-type]
        )

    assert outcome.value.verdict.status is AssessmentStatus.NOT_APPLICABLE
    assert FIXED_MARKER in outcome.value.verdict.reason
    assert requirement.required_evidence in outcome.value.verdict.reason
    assert "本地 CLI 不执行代表路径" in outcome.value.verdict.reason
    assert request.node.user_properties[0][1] == "不适用"
    assert model.environment.ledger.events[0] == (
        "pytest",
        "operator_evidence_required",
        {
            "source_case_id": requirement.source_case_id,
            "evidence_types": list(requirement.evidence_types),
            "required_evidence": requirement.required_evidence,
        },
    )
    assert model.environment.ledger.events[1][0:2] == (
        "assertion",
        "assessment_concluded",
    )


def test_unknown_case_is_rejected_before_recording_evidence() -> None:
    model = _Model()

    with pytest.raises(ValueError, match="未标记为需运营方举证"):
        OperatorEvidenceMotherCaseRunner().run_operator_evidence_case(
            source_case_id="TC-UNKNOWN",
            agent_model=model,  # type: ignore[arg-type]
            request=SimpleNamespace(node=SimpleNamespace(user_properties=[])),  # type: ignore[arg-type]
        )

    assert model.environment.ledger.events == []


def test_requirement_lookup_exposes_checked_in_details() -> None:
    requirement = operator_evidence_requirement("TC-5.5b-D1-01")

    assert requirement.evidence_types == ("访谈", "服务端证据")
    assert requirement.required_evidence.startswith("访谈要求：")
