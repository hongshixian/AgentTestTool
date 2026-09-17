"""Verify the checked-in black-box specification and thin case wrappers."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_black_box_cases.py"
MANIFEST = ROOT / "configs" / "black_box_cases.json"
WORKBOOK = (
    ROOT
    / "local_docs"
    / "测试用例集-三套卷版本"
    / "自动化测试三套卷_候选拆分.xlsx"
)
CLAUSES = ROOT / "agent_test_tool" / "reporting" / "clauses.json"
CASE_DIR = ROOT / "test_cases" / "black_box"

SPEC = importlib.util.spec_from_file_location("black_box_case_builder", BUILDER)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _constants(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id.isupper():
            constants[target.id] = ast.literal_eval(node.value)
    return constants


def test_checked_in_manifest_contains_exactly_the_42_black_box_cases() -> None:
    manifest = _manifest()
    cases = manifest["cases"]

    assert manifest["schema_version"] == "1.0"
    assert manifest["source_sheet"] == "01-测试题目"
    assert manifest["suite"] == "black_box"
    assert manifest["case_count"] == 42
    assert [case["case_id"] for case in cases] == [
        f"B{index:03d}" for index in range(1, 43)
    ]
    assert all(case["suite"] == "黑盒卷" for case in cases)
    assert all(case["input_config"]["Case_ID"] == case["case_id"] for case in cases)
    assert all("Pass" in case["verdict_expression"] for case in cases)
    assert all("Fail" in case["verdict_expression"] for case in cases)


def test_black_box_required_evidence_exposes_only_public_file_and_control() -> None:
    allowed_groups = {"PUBLIC", "FILE", "CONTROL"}

    for case in _manifest()["cases"]:
        groups = {
            line.partition(":")[0].strip()
            for line in case["required_evidence"].splitlines()
            if line.strip()
        }
        assert groups
        assert groups <= allowed_groups, case["case_id"]


@pytest.mark.skipif(not WORKBOOK.exists(), reason="local source workbook is not checked in")
def test_checked_in_manifest_is_reproducible_from_the_workbook() -> None:
    assert MODULE.build_manifest(WORKBOOK, CLAUSES) == _manifest()


def test_checked_in_wrappers_are_exactly_the_generated_set() -> None:
    cases = _manifest()["cases"]
    expected = {MODULE.wrapper_filename(case): case for case in cases}
    actual = {path.name: path for path in CASE_DIR.glob("test_b*.py")}

    assert set(actual) == set(expected)
    for filename, path in actual.items():
        case = expected[filename]
        assert path.read_text(encoding="utf-8") == MODULE.render_wrapper(case)
        constants = _constants(path)
        assert constants == {
            "TEST_CASE_ID": case["case_id"],
            "TEST_CASE_LEVEL": "black_box",
            "SECURITY_DOMAIN": case["security_domain"],
            "STANDARD_CLAUSE": case["standard_clause"],
            "CLAUSE_TITLE": case["clause_title"],
            "CLAUSE_ORIGINAL_TEXT": case["clause_original_text"],
            "CASE_TITLE": case["title"],
        }


def test_wrapper_contract_uses_static_markers_and_shared_runner() -> None:
    source = (CASE_DIR / "test_b001.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]

    assert "pytestmark = [pytest.mark.e2e, pytest.mark.black_box]" in source
    assert len(classes) == 1
    assert classes[0].name == "TestB001BlackBoxCase"
    assert isinstance(classes[0].bases[0], ast.Name)
    assert classes[0].bases[0].id == "BlackBoxCaseRunner"
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef)]
    assert [method.name for method in methods] == ["test_black_box_case"]
    assert "repeat_index" not in source
    assert "run_black_box_case(" in source


def test_generator_is_deterministic_and_refuses_unrelated_overwrite(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    first = MODULE.generate_wrappers(manifest, tmp_path)
    first_contents = {path.name: path.read_text(encoding="utf-8") for path in first}

    second = MODULE.generate_wrappers(manifest, tmp_path)
    assert {path.name: path.read_text(encoding="utf-8") for path in second} == first_contents

    first[0].write_text("user-owned content\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        MODULE.generate_wrappers(manifest, tmp_path)
