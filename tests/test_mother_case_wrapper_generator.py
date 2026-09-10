"""Verify deterministic generation of explicitly delegated mother cases."""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest

from test_cases.mother_cases.base import MotherCaseScenarioRunner


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_mother_case_wrappers.py"
MANIFEST = ROOT / "configs" / "mother_cases_v3.json"

SPEC = importlib.util.spec_from_file_location("mother_case_wrapper_generator", GENERATOR)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _constants(tree: ast.Module) -> dict[str, object]:
    result: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id.isupper():
            result[target.id] = ast.literal_eval(node.value)
    return result


def test_generator_writes_exactly_the_twelve_explicit_delegate_wrappers(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    delegate_cases = {
        case["source_case_id"]: case
        for case in manifest["cases"]
        if case["implementation_mode"] == "delegate"
    }

    generated = MODULE.generate_wrappers(manifest, tmp_path)

    assert len(generated) == 12
    assert {path.name for path in generated} == {
        MODULE.wrapper_filename(case) for case in delegate_cases.values()
    }
    for path in generated:
        source = path.read_text(encoding="utf-8")
        compile(source, path, "exec")
        tree = ast.parse(source)
        constants = _constants(tree)
        case = delegate_cases[constants["SOURCE_CASE_ID"]]
        assert constants["TEST_CASE_ID"] == case["source_case_id"]
        assert constants["TEST_CASE_LEVEL"] == "mother"
        assert constants["REPRESENTATIVE_CHILD_ID"] == case["representative_child_id"]
        assert constants["REPRESENTATIVE_CHILD_SCRIPT"] == case[
            "representative_child_script"
        ]


def test_every_delegate_path_is_resolvable_and_uses_supported_fixtures() -> None:
    supported = {"agent_model", "judge_model", "request", "repeat_index"}
    delegates = [
        case
        for case in _manifest()["cases"]
        if case["implementation_mode"] == "delegate"
    ]

    for case in delegates:
        _, method = MotherCaseScenarioRunner._resolve_representative(
            case["representative_child_script"],
            case["representative_child_id"],
        )
        fixtures = set(inspect.signature(method).parameters) - {"self"}
        assert fixtures <= supported


def test_generated_wrapper_follows_id_and_documentation_contract() -> None:
    case = next(
        case for case in _manifest()["cases"] if case["implementation_mode"] == "delegate"
    )

    source = MODULE.render_wrapper(case)
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]

    assert ast.get_docstring(tree) == (
        f"Run one representative path for mother case {case['source_case_id']}."
    )
    assert len(classes) == 1
    normalized_id = re.sub(r"[^A-Za-z0-9]", "", case["source_case_id"]).upper()
    assert classes[0].name == f"Test{normalized_id}MotherCase"
    class_doc = ast.get_docstring(classes[0]) or ""
    assert f"测试用例 ID：{case['source_case_id']}" in class_doc
    assert f"测试用例名称：{case['name']}" in class_doc
    assert all(
        heading in class_doc
        for heading in ("测试目标：", "前置条件：", "测试步骤：", "预期结果：")
    )
    methods = [
        node
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    assert [method.name for method in methods] == ["test_representative_child_path"]


def test_pending_case_cannot_be_rendered_or_mechanically_generated(tmp_path: Path) -> None:
    manifest = _manifest()
    pending = dict(
        next(
            case
            for case in manifest["cases"]
            if case["implementation_mode"] == "deferred"
        )
    )
    pending["implementation_mode"] = "pending"

    with pytest.raises(ValueError, match="not explicitly marked for delegation"):
        MODULE.render_wrapper(pending)

    generated = MODULE.generate_wrappers({"cases": [pending]}, tmp_path)
    assert generated == ()
    assert list(tmp_path.iterdir()) == []


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
