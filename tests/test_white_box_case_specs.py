"""Verify the generated white-box placeholder case set."""

from pathlib import Path

from scripts.build_white_box_cases import (
    EXPECTED_CASE_IDS, IMPLEMENTED_CASE_IDS, build_manifest, render_wrapper,
)


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "local_docs" / "测试用例集-三套卷版本" / "自动化测试三套卷_候选拆分.xlsx"
CLAUSES = ROOT / "agent_test_tool" / "reporting" / "clauses.json"


def test_white_box_manifest_matches_the_reviewed_workbook_scope() -> None:
    manifest = build_manifest(WORKBOOK, CLAUSES)

    assert manifest["case_count"] == 86
    assert tuple(case["case_id"] for case in manifest["cases"]) == EXPECTED_CASE_IDS


def test_white_box_wrappers_match_implementation_status() -> None:
    paths = sorted((ROOT / "test_cases" / "white_box").glob("test_w*.py"))

    assert len(paths) == 86
    for path, case_id in zip(paths, EXPECTED_CASE_IDS, strict=True):
        source = path.read_text(encoding="utf-8")
        assert f'TEST_CASE_ID = "{case_id}"' in source
        assert 'TEST_CASE_LEVEL = "white_box"' in source
        assert "send_prompt" not in source
        if case_id in IMPLEMENTED_CASE_IDS:
            assert 'IMPLEMENTATION_MODE = "implemented"' in source
            assert "execute_w062_case" in source
            assert "conclude_not_applicable" not in source
            assert "当前暂未实现" not in source
        else:
            assert "conclude_not_applicable" in source
            assert "当前暂未实现" in source


def test_generated_wrapper_is_reproducible() -> None:
    case = build_manifest(WORKBOOK, CLAUSES)["cases"][0]

    assert render_wrapper(case) == (
        ROOT / "test_cases" / "white_box" / "test_w001.py"
    ).read_text(encoding="utf-8")


def test_manifest_marks_only_w062_as_implemented() -> None:
    manifest = build_manifest(WORKBOOK, CLAUSES)
    cases = {case["case_id"]: case for case in manifest["cases"]}

    assert manifest["implemented_case_ids"] == ["W062"]
    assert cases["W062"]["deferred_reason"] == ""
    assert all(
        case["deferred_reason"]
        for case_id, case in cases.items()
        if case_id != "W062"
    )
