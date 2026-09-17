"""Verify reviewed black-box parallel classification fails closed on changes."""

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


def test_reviewed_black_box_cases_have_valid_dependencies():
    manifest = policy._manifest()
    assert len(manifest["cases"]) == 42
    assert set(manifest["cases"]) == {
        f"test_cases/black_box/test_b{index:03d}.py" for index in range(1, 43)
    }
    for script in manifest["cases"]:
        assert policy.case_execution_policy(policy.ROOT / script)[0] == "isolated", script


def test_unknown_cases_remain_exclusive(tmp_path: Path):
    assert policy.case_execution_policy(tmp_path / "test_unknown.py")[0] == "exclusive"
    assert policy.case_execution_policy(
        policy.ROOT / "test_cases/smoke/test_agent_identity.py"
    )[0] == "exclusive"


def test_changed_shared_dependency_falls_back_to_exclusive(monkeypatch):
    path = policy.ROOT / "test_cases/black_box/test_b001.py"
    original = policy._digest
    monkeypatch.setattr(
        policy,
        "_digest",
        lambda candidate: "changed" if candidate.name == "scenario_handlers.py" else original(candidate),
    )
    assert policy.case_execution_policy(path)[0] == "exclusive"


def test_missing_manifest_falls_back_to_exclusive(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "MANIFEST", tmp_path / "missing.json")
    assert policy.case_execution_policy(
        policy.ROOT / "test_cases/black_box/test_b001.py"
    )[0] == "exclusive"
