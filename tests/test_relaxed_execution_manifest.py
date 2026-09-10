"""Verify the stage-2 relaxed execution manifest stays workbook-aligned."""

import importlib.util
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
STAGE2_ROOT = ROOT / "local_docs/可执行率优化/阶段2"
BUILDER = STAGE2_ROOT / "build_relaxed_execution_manifest.py"
WORKBOOK = STAGE2_ROOT / "全4256_E类放宽复核.xlsx"

if not BUILDER.is_file() or not WORKBOOK.is_file():
    pytest.skip(
        "stage-2 source workbook and builder are local review artifacts",
        allow_module_level=True,
    )

SPEC = importlib.util.spec_from_file_location("stage2_manifest_builder", BUILDER)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
LABEL_PREFIXES = MODULE.LABEL_PREFIXES
_read_workbook = MODULE._read_workbook
build_manifest = MODULE.build_manifest


def test_stage2_workbook_contains_expected_case_rows_and_labels() -> None:
    rows = _read_workbook(WORKBOOK)

    assert len(rows) == 4256
    assert {row["判定标签"].split(" ", 1)[0] for row in rows.values()} >= LABEL_PREFIXES
    assert rows["ATS-6.1b-D5-01-S01-01"]["明确FAIL条件"]


def test_stage2_manifest_aligns_scripts_and_ids() -> None:
    manifest = build_manifest(ROOT, WORKBOOK)

    assert manifest["candidate_count"] == 231
    assert manifest["by_label"] == {"B": 167, "G": 64}
    for case in manifest["cases"]:
        source = (ROOT / case["script"]).read_text(encoding="utf-8")
        match = re.search(r"TEST_CASE_ID\s*=\s*['\"]([^'\"]+)", source)
        assert match is not None
        assert match.group(1) == case["case_id"]
        assert f"test_cases.scenarios.{case['runner']}" in source
        assert f"{case['runner']}" in source
        assert case["runner"]
        assert case["fail_condition"]


def test_stage2_manifest_only_counts_relaxed_shared_runners() -> None:
    manifest = build_manifest(ROOT, WORKBOOK)

    assert manifest["criterion"].startswith("shared runner contains")
    assert all(
        "conclude_relaxed_passed"
        in (ROOT / "test_cases" / "scenarios" / f"{case['runner']}.py").read_text(
            encoding="utf-8"
        )
        for case in manifest["cases"]
    )
