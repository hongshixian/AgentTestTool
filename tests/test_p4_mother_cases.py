"""Verify the frozen contract for all CLI-excluded P4 mother cases."""

from __future__ import annotations

import ast
from collections import Counter
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "mother_cases_v3.json"
MOTHER_ROOT = ROOT / "test_cases" / "mother_cases"
EXPECTED_PROFILE_COUNTS = {
    "device_ui": 28,
    "files_and_sink": 1,
    "risk_notice": 2,
    "risk_action": 4,
    "cancel_task": 1,
}


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _p4_cases() -> list[dict[str, object]]:
    payload = _manifest()
    cases = payload["cases"]
    assert isinstance(cases, list)
    return [case for case in cases if case["priority"] == "P4"]


def _wrapper_path(source_case_id: str) -> Path:
    normalized = re.sub(r"[^a-z0-9]+", "_", source_case_id.lower()).strip("_")
    return MOTHER_ROOT / f"test_{normalized}.py"


def _literal_assignments(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            values[target.id] = ast.literal_eval(node.value)
        except (TypeError, ValueError):
            continue
    return values


def _execution_profile(case: dict[str, object]) -> str:
    required = str(case["required_capability"])
    return required.split("：", maxsplit=1)[0].strip()


def test_frozen_manifest_contains_exact_p4_population_and_exclusion_policy() -> None:
    payload = _manifest()
    source = payload["source"]
    assert isinstance(source, dict)
    assert source["sheet"] == "01-用例总表"

    cases = _p4_cases()
    assert len(cases) == 36
    assert Counter(str(case["category"]) for case in cases) == {"H": 36}
    assert {str(case["arrangement"]) for case in cases} == {"排除-UI设备"}
    assert all("本轮CLI不下发" in str(case["test_input"]) for case in cases)
    assert all("本轮不产出FAIL" in str(case["fail_condition"]) for case in cases)
    assert all("本轮不产出PASS" in str(case["pass_condition"]) for case in cases)


def test_each_p4_case_has_one_normalized_wrapper_with_frozen_metadata() -> None:
    cases = _p4_cases()
    expected_paths = {
        _wrapper_path(str(case["source_case_id"])) for case in cases
    }
    actual_paths = {
        path
        for path in MOTHER_ROOT.glob("test_tc_*.py")
        if _literal_assignments(path).get("PRIORITY") == "P4"
    }
    assert actual_paths == expected_paths

    wrapper_profiles: Counter[str] = Counter()
    for case in cases:
        source_case_id = str(case["source_case_id"])
        path = _wrapper_path(source_case_id)
        assert path.is_file(), source_case_id

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        methods = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        assert len(methods) == 1, source_case_id

        values = _literal_assignments(path)
        expected_profile = _execution_profile(case)
        assert values["TEST_CASE_ID"] == source_case_id
        assert values["TEST_CASE_LEVEL"] == "mother"
        assert values["SOURCE_CASE_ID"] == source_case_id
        assert values["PRIORITY"] == "P4"
        assert values["CATEGORY"] == "H"
        assert values["IMPLEMENTATION_MODE"] == "deferred"
        assert values["REQUIRED_CAPABILITY"] == case["required_capability"]
        assert values["EXECUTION_PROFILE"] == expected_profile
        assert not str(values.get("REPRESENTATIVE_CHILD_ID") or "")
        assert not str(values.get("REPRESENTATIVE_CHILD_SCRIPT") or "")
        wrapper_profiles[expected_profile] += 1

    assert dict(wrapper_profiles) == EXPECTED_PROFILE_COUNTS


def test_manifest_keeps_nonempty_child_traceability_for_every_p4_case() -> None:
    for case in _p4_cases():
        source_case_id = str(case["source_case_id"])
        source_suffix = source_case_id.removeprefix("TC-")
        candidates = case["representative_child_candidates"]
        assert isinstance(candidates, list)
        assert candidates, source_case_id

        for candidate in candidates:
            candidate_id = str(candidate["case_id"])
            candidate_script = str(candidate["script"])
            assert candidate_id.startswith(f"ATS-{source_suffix}-S"), candidate_id
            assert candidate_script.startswith("test_cases/test_")
            assert (ROOT / candidate_script).is_file(), candidate_script


def test_manifest_capabilities_derive_the_exact_p4_profile_distribution() -> None:
    derived = Counter(_execution_profile(case) for case in _p4_cases())

    assert dict(derived) == EXPECTED_PROFILE_COUNTS
