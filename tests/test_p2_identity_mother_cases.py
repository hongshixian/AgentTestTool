"""Verify P2 B/C mother-case selection and capability routing offline."""

from __future__ import annotations

import ast
from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.mother_cases.base import MotherCaseScenarioRunner
from test_cases.mother_cases.p2_identity import (
    P2IdentityMotherCaseRunner,
    required_capability_key,
)
from test_cases.mother_cases.p2_proxy import (
    P2_BC_PROFILE_BY_SOURCE_CASE,
    P2ProxyMotherCaseRunner,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "mother_cases_v3.json"
WRAPPER_ROOT = ROOT / "test_cases" / "mother_cases"


class _Ledger:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    def record(self, *values: object) -> None:
        self.events.append(values)


class _Model:
    def __init__(self) -> None:
        self.capabilities = SimpleNamespace()
        self.environment = SimpleNamespace(ledger=_Ledger())


def _request() -> SimpleNamespace:
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


def _p2_cases() -> list[dict[str, object]]:
    cases = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    return [
        case
        for case in cases
        if case["priority"] == "P2" and case["category"] in {"B", "C"}
    ]


def _wrapper_path(source_case_id: str) -> Path:
    stem = "test_" + source_case_id.lower().replace("-", "_").replace(".", "_")
    return WRAPPER_ROOT / f"{stem}.py"


def _literal_assignments(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            try:
                values[target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
    return values


def test_all_98_wrappers_freeze_valid_nonblind_representative_selections() -> None:
    cases = _p2_cases()
    assert len(cases) == 98
    nonfirst_selections = 0

    for case in cases:
        source_case_id = str(case["source_case_id"])
        path = _wrapper_path(source_case_id)
        assert path.is_file(), source_case_id
        values = _literal_assignments(path)
        selected = (
            values["REPRESENTATIVE_CHILD_ID"],
            values["REPRESENTATIVE_CHILD_SCRIPT"],
        )
        candidates = [
            (candidate["case_id"], candidate["script"])
            for candidate in case["representative_child_candidates"]
        ]
        assert selected in candidates, source_case_id
        nonfirst_selections += selected != candidates[0]
        assert values["TEST_CASE_ID"] == source_case_id
        assert values["PRIORITY"] == "P2"
        assert values["CATEGORY"] in {"B", "C"}
        assert values["IMPLEMENTATION_MODE"] == "p2_identity"
        MotherCaseScenarioRunner._resolve_representative(*reversed(selected))

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        test_methods = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        ]
        assert len(test_methods) == 1, source_case_id

    assert nonfirst_selections >= 20


def test_selected_paths_pin_semantically_specific_nonfirst_candidates() -> None:
    expected = {
        "TC-6.2a-D2-02": "ATS-6.2a-D2-02-S02-01",
        "TC-6.2a-D5-01": "ATS-6.2a-D5-01-S04-08",
        "TC-6.2c-D5-01": "ATS-6.2c-D5-01-S01-03",
        "TC-6.2d-D2-01": "ATS-6.2d-D2-01-S01-02",
        "TC-6.2h-D2-01": "ATS-6.2h-D2-01-S03-01",
        "TC-6.4c-D2-02": "ATS-6.4c-D2-02-S03-08",
        "TC-7.1c-D2-02": "ATS-7.1c-D2-02-S01-09",
        "TC-7.2c-D4-01": "ATS-7.2c-D4-01-S01-06",
    }

    for source_case_id, child_id in expected.items():
        values = _literal_assignments(_wrapper_path(source_case_id))
        assert values["REPRESENTATIVE_CHILD_ID"] == child_id


def test_profile_audit_freezes_32_real_9_required_na_and_57_unmapped() -> None:
    cases = _p2_cases()
    source_ids = {str(case["source_case_id"]) for case in cases}
    mapped_ids = set(P2_BC_PROFILE_BY_SOURCE_CASE)
    distribution = Counter(P2_BC_PROFILE_BY_SOURCE_CASE.values())

    assert mapped_ids <= source_ids
    assert len(mapped_ids) == 41
    assert len(source_ids - mapped_ids) == 57
    assert distribution == {
        "tool_minimization": 8,
        "permission_deny": 5,
        "permission_binding": 4,
        "protocol_route": 1,
        "tool_return_boundary": 4,
        "risk_action": 5,
        "risk_notice": 2,
        "cancel_task": 3,
        "not_applicable": 9,
    }
    assert sum(count for profile, count in distribution.items() if profile != "not_applicable") == 32


def test_required_na_profile_set_is_exact() -> None:
    assert {
        source_case_id
        for source_case_id, profile in P2_BC_PROFILE_BY_SOURCE_CASE.items()
        if profile == "not_applicable"
    } == {
        "TC-6.2c-D5-02",
        "TC-6.2d-D2-02",
        "TC-6.2e-D2-01",
        "TC-6.2e-D5-02",
        "TC-6.4b-D2-02",
        "TC-6.4d-D2-01",
        "TC-6.4f-D2-01",
        "TC-6.4f-D2-02",
        "TC-7.2c-D4-02",
    }


def test_unsupported_product_capability_concludes_not_applicable() -> None:
    runner = P2IdentityMotherCaseRunner()

    with pytest.raises(AssessmentOutcomeSignal) as outcome:
        runner.run_p2_bc_case(
            source_case_id="TC-5.1a-D2-01",
            representative_child_id="ATS-5.1a-D2-01-S01-01",
            representative_child_script=(
                "test_cases/test_cross_account_instance_identifier_reuse.py"
            ),
            agent_model=_Model(),  # type: ignore[arg-type]
            judge_model=None,
            request=_request(),  # type: ignore[arg-type]
            repeat_index=1,
        )

    assert outcome.value.verdict.status is AssessmentStatus.NOT_APPLICABLE
    assert "不使用模型自述" in outcome.value.verdict.reason
    assert "instance_api" in outcome.value.verdict.reason


def test_all_57_unmapped_cases_report_missing_real_public_interface() -> None:
    mapped_ids = set(P2_BC_PROFILE_BY_SOURCE_CASE)
    for case in _p2_cases():
        source_case_id = str(case["source_case_id"])
        if source_case_id in mapped_ids:
            continue
        values = _literal_assignments(_wrapper_path(source_case_id))
        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            P2IdentityMotherCaseRunner().run_p2_bc_case(
                source_case_id=source_case_id,
                representative_child_id=str(values["REPRESENTATIVE_CHILD_ID"]),
                representative_child_script=str(values["REPRESENTATIVE_CHILD_SCRIPT"]),
                agent_model=_Model(),  # type: ignore[arg-type]
                judge_model=None,
                request=_request(),  # type: ignore[arg-type]
                repeat_index=1,
            )

        reason = outcome.value.verdict.reason
        assert outcome.value.verdict.status is AssessmentStatus.NOT_APPLICABLE
        assert required_capability_key(case) in reason
        assert "不使用模型自述" in reason


def test_all_9_mapped_na_cases_report_non_substitutable_product_interface() -> None:
    for source_case_id, profile in P2_BC_PROFILE_BY_SOURCE_CASE.items():
        if profile != "not_applicable":
            continue
        values = _literal_assignments(_wrapper_path(source_case_id))
        case = next(
            case for case in _p2_cases() if case["source_case_id"] == source_case_id
        )
        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            P2IdentityMotherCaseRunner().run_p2_bc_case(
                source_case_id=source_case_id,
                representative_child_id=str(values["REPRESENTATIVE_CHILD_ID"]),
                representative_child_script=str(values["REPRESENTATIVE_CHILD_SCRIPT"]),
                agent_model=_Model(),  # type: ignore[arg-type]
                judge_model=None,
                request=_request(),  # type: ignore[arg-type]
                repeat_index=1,
            )

        reason = outcome.value.verdict.reason
        assert outcome.value.verdict.status is AssessmentStatus.NOT_APPLICABLE
        assert str(case["required_capability"]) in reason
        assert "不能用测试侧模拟物替代" in reason


def test_all_32_real_profiles_route_to_proxy_instead_of_legacy_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, object]] = []

    def fake_proxy(_self: object, **kwargs: object) -> None:
        captured.append(dict(kwargs))

    monkeypatch.setattr(
        P2ProxyMotherCaseRunner,
        "run_p2_proxy_case",
        fake_proxy,
    )
    real_profiles = {
        source_case_id: profile
        for source_case_id, profile in P2_BC_PROFILE_BY_SOURCE_CASE.items()
        if profile != "not_applicable"
    }
    for source_case_id, expected_profile in real_profiles.items():
        values = _literal_assignments(_wrapper_path(source_case_id))
        model = _Model()
        request = _request()
        P2IdentityMotherCaseRunner().run_p2_bc_case(
            source_case_id=source_case_id,
            representative_child_id=str(values["REPRESENTATIVE_CHILD_ID"]),
            representative_child_script=str(values["REPRESENTATIVE_CHILD_SCRIPT"]),
            agent_model=model,  # type: ignore[arg-type]
            judge_model=None,
            request=request,  # type: ignore[arg-type]
            repeat_index=3,
        )
        assert captured[-1]["source_case_id"] == source_case_id
        assert captured[-1]["profile"] == expected_profile
        assert captured[-1]["agent_model"] is model
        assert captured[-1]["request"] is request
        assert model.environment.ledger.events[-1][2]["execution_mode"] == (
            f"p2_proxy:{expected_profile}"
        )

    assert len(captured) == 32


def test_runner_rejects_child_outside_manifest_candidate_set() -> None:
    with pytest.raises(ValueError, match="不在 manifest 候选集"):
        P2IdentityMotherCaseRunner().run_p2_bc_case(
            source_case_id="TC-6.2d-D2-01",
            representative_child_id="ATS-NOT-A-CANDIDATE",
            representative_child_script="test_cases/test_record_search_mcp_protocol_invocation.py",
            agent_model=_Model(),  # type: ignore[arg-type]
            judge_model=None,
            request=_request(),  # type: ignore[arg-type]
            repeat_index=1,
        )
