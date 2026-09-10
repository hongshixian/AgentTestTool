"""Verify the checked-in mother-case manifest and its reproducible builder."""

from __future__ import annotations

import importlib.util
import json
import re
from copy import deepcopy
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_mother_case_manifest.py"
MANIFEST = ROOT / "configs" / "mother_cases_v3.json"
WORKBOOK = (
    ROOT
    / "local_docs"
    / "CLI宽松判定版_v3"
    / "智能体应用安全评测用例集_CLI宽松判定版_v3.xlsx"
)
P1_INVENTORY = ROOT / "docs" / "p1_mother_case_inventory.md"

SPEC = importlib.util.spec_from_file_location("mother_case_manifest_builder", BUILDER)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _checked_in_manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_checked_in_manifest_is_complete_and_valid_without_local_docs() -> None:
    manifest = _checked_in_manifest()

    MODULE.validate_manifest(manifest)
    assert manifest["case_count"] == 385
    assert manifest["priority_counts"] == {
        "P1": 47,
        "P2": 242,
        "P3": 60,
        "P4": 36,
    }
    assert manifest["category_counts"] == {
        "B": 96,
        "C": 8,
        "D": 9,
        "E": 49,
        "F": 11,
        "G": 118,
        "H": 36,
        "I": 14,
        "J": 44,
    }


def test_manifest_has_required_source_and_assessment_fields() -> None:
    cases = _checked_in_manifest()["cases"]
    required = {
        "source_case_id",
        "name",
        "category",
        "priority",
        "arrangement",
        "required_capability",
        "pass_condition",
        "fail_condition",
        "uncovered_requirements",
        "experiment_reuse_key",
    }

    assert all(required <= set(case) for case in cases)
    assert all(case["name"] for case in cases)
    assert all(case["pass_condition"] for case in cases)
    assert all(case["fail_condition"] for case in cases)
    assert all(case["experiment_reuse_key"].startswith("TC-") for case in cases)
    assert [case["priority"] for case in cases] == sorted(
        case["priority"] for case in cases
    )


def test_child_candidates_exist_and_encode_the_same_mother_case() -> None:
    cases = _checked_in_manifest()["cases"]

    assert sum(case["child_case_count"] for case in cases) == 4264
    assert all(case["child_case_count"] > 0 for case in cases)
    for case in cases:
        source_prefix = case["source_case_id"].removeprefix("TC-")
        for child in case["representative_child_candidates"]:
            assert child["case_id"].startswith(f"ATS-{source_prefix}-S")
            assert (ROOT / child["script"]).is_file()


def test_mother_implementation_metadata_is_read_without_importing_wrappers(
    tmp_path: Path,
) -> None:
    mother_root = tmp_path / "test_cases" / "mother_cases"
    mother_root.mkdir(parents=True)
    wrapper = mother_root / "test_tc_example.py"
    wrapper.write_text(
        "TEST_CASE_ID = 'TC-EXAMPLE'\n"
        "REPRESENTATIVE_CHILD_ID = 'ATS-EXAMPLE-S01-01'\n"
        "REPRESENTATIVE_CHILD_SCRIPT = 'test_cases/test_example.py'\n"
        "IMPLEMENTATION_MODE = 'p2_output'\n"
        "raise RuntimeError('must not import')\n",
        encoding="utf-8",
    )

    assert MODULE.find_mother_implementations(tmp_path) == {
        "TC-EXAMPLE": {
            "representative_child_id": "ATS-EXAMPLE-S01-01",
            "representative_child_script": "test_cases/test_example.py",
            "implementation_mode": "p2_output",
        }
    }


def test_all_p1_representatives_match_the_curated_inventory() -> None:
    cases = {
        case["source_case_id"]: case
        for case in _checked_in_manifest()["cases"]
        if case["priority"] == "P1"
    }

    assert set(cases) == set(MODULE.P1_REPRESENTATIVE_PATHS)
    assert {
        mode: sum(case["implementation_mode"] == mode for case in cases.values())
        for mode in MODULE.EXPECTED_P1_MODE_COUNTS
    } == MODULE.EXPECTED_P1_MODE_COUNTS
    for source_case_id, (child_id, script, mode) in MODULE.P1_REPRESENTATIVE_PATHS.items():
        case = cases[source_case_id]
        assert case["representative_child_id"] == child_id
        assert case["representative_child_script"] == script
        assert case["implementation_mode"] == MODULE._p1_implementation_mode(
            source_case_id,
            mode,
        )
        assert {"case_id": child_id, "script": script} in case[
            "representative_child_candidates"
        ]


def test_curated_p1_mapping_matches_the_documented_inventory() -> None:
    documented: dict[str, tuple[str, str, str]] = {}
    for line in P1_INVENTORY.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\|\s*\d+\s*\|", line) is None:
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        mother_match = re.search(r"`(TC-[^`]+)`", columns[2])
        child_match = re.search(r"`(ATS-[^`]+)`\s+`([^`]+)`", columns[3])
        assert mother_match is not None and child_match is not None
        documented[mother_match.group(1)] = (
            child_match.group(1),
            f"test_cases/{child_match.group(2)}",
            "delegate" if columns[5] == "是" else "pending",
        )

    assert documented == MODULE.P1_REPRESENTATIVE_PATHS


def test_p2_representatives_are_selected_from_their_generated_wrappers() -> None:
    cases = [
        case
        for case in _checked_in_manifest()["cases"]
        if case["priority"] == "P2"
    ]

    assert len(cases) == 242
    assert {
        mode: sum(case["implementation_mode"] == mode for case in cases)
        for mode in ("p2_identity", "p2_proxy", "p2_output")
    } == {
        "p2_identity": 98,
        "p2_proxy": 100,
        "p2_output": 44,
    }
    assert all(case["representative_child_id"] for case in cases)
    assert all(case["representative_child_script"] for case in cases)


def test_p3_and_p4_representatives_remain_pending_and_unselected() -> None:
    cases = [
        case
        for case in _checked_in_manifest()["cases"]
        if case["priority"] in {"P3", "P4"}
    ]

    assert len(cases) == 96
    assert all(case["implementation_mode"] == "pending" for case in cases)
    assert all(case["representative_child_id"] is None for case in cases)
    assert all(case["representative_child_script"] is None for case in cases)


@pytest.mark.parametrize("missing_field", ("representative_child_id", "representative_child_script"))
def test_manifest_rejects_unpaired_representative_fields(missing_field: str) -> None:
    manifest = deepcopy(_checked_in_manifest())
    case = next(case for case in manifest["cases"] if case["implementation_mode"] == "delegate")
    case[missing_field] = None

    with pytest.raises(ValueError, match="must be paired"):
        MODULE.validate_manifest(manifest)


def test_manifest_rejects_representative_outside_candidates() -> None:
    manifest = deepcopy(_checked_in_manifest())
    case = next(case for case in manifest["cases"] if case["implementation_mode"] == "delegate")
    case["representative_child_script"] = "test_cases/test_not_the_selected_child.py"

    with pytest.raises(ValueError, match="not a listed candidate"):
        MODULE.validate_manifest(manifest)


@pytest.mark.skipif(not WORKBOOK.is_file(), reason="local v3 workbook is unavailable")
def test_checked_in_manifest_is_reproducible_from_v3_workbook() -> None:
    rebuilt = MODULE.build_manifest(ROOT, WORKBOOK)

    assert rebuilt == _checked_in_manifest()
