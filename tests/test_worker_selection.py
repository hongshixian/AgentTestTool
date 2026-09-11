"""Verify exact worker selection using real, offline pytest subprocesses."""

import json

import pytest


pytest_plugins = ("pytester",)


def test_collect_then_select_preserves_parameterized_ids_and_metadata(pytester):
    pytester.makepyfile(test_sample='''
import pytest
TEST_CASE_ID = "TC-5.1a-D1-01"
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = TEST_CASE_ID

@pytest.fixture
def execution_only():
    from pathlib import Path
    Path("executed").touch()

@pytest.mark.parametrize("repeat_index", [0, 1, 2])
def test_sample(repeat_index, execution_only):
    assert repeat_index != 1
''')
    inventory = pytester.path / "inventory.json"
    args = ["-p", "agent_test_tool.result_plugin", "--agent-result-json"]
    result = pytester.runpytest_subprocess(*args, str(inventory), "--collect-only", "-q")
    assert result.ret == 0
    assert not (pytester.path / "executed").exists()
    cases = json.loads(inventory.read_text())["cases"]
    assert len(cases) == 3
    selection = pytester.path / "selection.json"
    selection.write_text(json.dumps([cases[0]["nodeid"], cases[2]["nodeid"]]))
    output = pytester.path / "worker.json"
    result = pytester.runpytest_subprocess(
        *args, str(output), "--agent-nodeids-file", str(selection), "-q"
    )
    result.assert_outcomes(passed=2, deselected=1)
    payload = json.loads(output.read_text())
    assert payload["session"]["collected"] == 2
    assert [item["nodeid"] for item in payload["cases"]] == [cases[0]["nodeid"], cases[2]["nodeid"]]
    assert all(item["case_level"] == "mother" for item in payload["cases"])
    assert (pytester.path / "executed").exists()


@pytest.mark.parametrize("selection", [[], ["x", "x"], [42], {}, ["missing.py::test_missing"]])
def test_invalid_or_stale_selection_never_executes_tests(pytester, selection):
    pytester.makepyfile('''
def test_must_not_run():
    from pathlib import Path
    Path("executed").touch()
''')
    path = pytester.path / "selection.json"
    path.write_text(json.dumps(selection))
    result = pytester.runpytest_subprocess(
        "-p", "agent_test_tool.result_plugin", "--agent-result-json", "result.json",
        "--agent-nodeids-file", str(path), "-q",
    )
    assert result.ret != 0
    assert not (pytester.path / "executed").exists()


def test_worker_selection_cannot_override_marker_filter(pytester):
    pytester.makepyfile('''
def test_excluded():
    from pathlib import Path
    Path("executed").touch()
''')
    selection = pytester.path / "selection.json"
    selection.write_text(json.dumps(["test_worker_selection_cannot_override_marker_filter.py::test_excluded"]))
    result = pytester.runpytest_subprocess(
        "-p", "agent_test_tool.result_plugin", "--agent-result-json", "result.json",
        "--agent-nodeids-file", str(selection), "-m", "nonexistent", "-q",
    )
    assert result.ret != 0
    assert not (pytester.path / "executed").exists()


def test_parallel_worker_rechecks_review_before_execution(pytester):
    pytester.makepyfile('''
def test_unreviewed():
    from pathlib import Path
    Path("executed").touch()
''')
    result = pytester.runpytest_subprocess(
        "-p", "agent_test_tool.result_plugin", "--agent-result-json", "result.json",
        "--agent-require-isolated", "-q",
    )
    assert result.ret != 0
    assert not (pytester.path / "executed").exists()
