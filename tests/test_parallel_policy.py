"""Verify reviewed classification and conservative fallback for changed code."""

from pathlib import Path

import pytest

from agent_test_tool import parallel_policy as policy


@pytest.fixture(autouse=True)
def clear_policy_caches():
    policy._digest.cache_clear()
    policy._manifest.cache_clear()
    yield
    policy._digest.cache_clear()
    policy._manifest.cache_clear()


def test_reviewed_cases_have_valid_dependencies_and_cover_both_suites():
    manifest = policy._manifest()
    for script in manifest["cases"]:
        assert policy.case_execution_policy(policy.ROOT / script)[0] == "isolated", script
    assert sum("mother_cases/" in script for script in manifest["cases"]) >= 190
    assert sum("mother_cases/" not in script for script in manifest["cases"]) >= 200


def test_unknown_and_shared_memory_cases_remain_exclusive(tmp_path):
    assert policy.case_execution_policy(tmp_path / "test_unknown.py")[0] == "exclusive"
    for script in (
        "test_cases/mother_cases/test_tc_5_2c_d3_01.py",
        "test_cases/scenarios/output_detection_boundary_d4.py",
        "test_cases/mother_cases/test_tc_7_2c_d2_01.py",
    ):
        assert policy.case_execution_policy(policy.ROOT / script)[0] == "exclusive"


def test_changed_dependency_falls_back_to_exclusive(monkeypatch):
    path = policy.ROOT / "test_cases/mother_cases/test_tc_6_2a_d2_01.py"
    original = policy._digest
    monkeypatch.setattr(
        policy, "_digest", lambda candidate: "changed" if candidate.name == "p2_proxy.py" else original(candidate)
    )
    assert policy.case_execution_policy(path)[0] == "exclusive"
    monkeypatch.undo()


def test_missing_manifest_falls_back_to_exclusive(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "MANIFEST", tmp_path / "missing.json")
    assert policy.case_execution_policy(policy.ROOT / "test_cases/test_unknown.py")[0] == "exclusive"
