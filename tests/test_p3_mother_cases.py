"""Verify the frozen contract for all deferred P3 mother cases."""

from __future__ import annotations

import ast
from collections import Counter
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "mother_cases_v3.json"
MOTHER_ROOT = ROOT / "test_cases" / "mother_cases"
EXPECTED_ARRANGEMENTS = {"暂缓-过程取证", "暂缓-材料规则"}
EXPECTED_PROFILE_COUNTS = {
    "product_audit": 37,
    "material": 14,
    "device_ui": 3,
    "instance_api": 2,
    "component_loader": 1,
    "extension_loader": 1,
    "route_observation": 1,
    "risk_action": 1,
}


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _p3_cases() -> list[dict[str, object]]:
    payload = _manifest()
    cases = payload["cases"]
    assert isinstance(cases, list)
    return [case for case in cases if case["priority"] == "P3"]


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


def test_frozen_manifest_contains_exact_p3_population_and_policy_text() -> None:
    payload = _manifest()
    source = payload["source"]
    assert isinstance(source, dict)
    assert source["sheet"] == "01-用例总表"

    cases = _p3_cases()
    assert len(cases) == 60
    assert Counter(str(case["category"]) for case in cases) == {"E": 49, "F": 11}
    assert {str(case["arrangement"]) for case in cases} == EXPECTED_ARRANGEMENTS
    assert all(
        case["arrangement"]
        == ("暂缓-过程取证" if case["category"] == "E" else "暂缓-材料规则")
        for case in cases
    )
    assert all("本轮不产出FAIL" in str(case["fail_condition"]) for case in cases)
    assert all("本轮不产出PASS" in str(case["pass_condition"]) for case in cases)


def test_each_p3_case_has_one_normalized_wrapper_with_frozen_metadata() -> None:
    cases = _p3_cases()
    expected_paths = {
        _wrapper_path(str(case["source_case_id"])) for case in cases
    }
    actual_paths = {
        path
        for path in MOTHER_ROOT.glob("test_tc_*.py")
        if _literal_assignments(path).get("PRIORITY") == "P3"
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
        assert values["PRIORITY"] == "P3"
        assert values["CATEGORY"] == case["category"]
        assert values["IMPLEMENTATION_MODE"] == "deferred"
        assert values["REQUIRED_CAPABILITY"] == case["required_capability"]
        assert values["EXECUTION_PROFILE"] == expected_profile
        wrapper_profiles[expected_profile] += 1

        representative_id = str(values.get("REPRESENTATIVE_CHILD_ID") or "")
        representative_script = str(
            values.get("REPRESENTATIVE_CHILD_SCRIPT") or ""
        )
        assert bool(representative_id) == bool(representative_script), source_case_id
        if representative_id:
            candidates = {
                (str(candidate["case_id"]), str(candidate["script"]))
                for candidate in case["representative_child_candidates"]
            }
            assert (representative_id, representative_script) in candidates
        if case["category"] == "F":
            assert not representative_id
            assert not representative_script

    assert dict(wrapper_profiles) == EXPECTED_PROFILE_COUNTS


def test_manifest_capabilities_derive_the_exact_p3_profile_distribution() -> None:
    derived = Counter(_execution_profile(case) for case in _p3_cases())

    assert dict(derived) == EXPECTED_PROFILE_COUNTS
