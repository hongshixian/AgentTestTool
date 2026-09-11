"""Exercise real worker subprocesses without invoking a target Agent or Judge."""

from __future__ import annotations

import json
from pathlib import Path
from contextlib import contextmanager
import subprocess
import threading
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agent_models.processes import run_managed_process
from agent_models.processes import ProcessCleanupError
from agent_models.factory import AgentModelFactory
from agent_test_tool.parallel_runner import run_parallel_business
from agent_test_tool.runner import WorkflowConfig


pytest_plugins = ("pytester",)


def test_four_real_workers_overlap_and_exclusive_waits(pytester, monkeypatch):
    barrier = threading.Barrier(4, timeout=15)
    finished: set[str] = set()
    profiles: set[str] = set()
    lock = threading.Lock()
    events: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            name = data["name"]
            if name == "exclusive":
                with lock:
                    valid = len(finished) == 4
                    events.append("exclusive")
            else:
                with lock:
                    profiles.add(data["profile"])
                    events.append(name)
                try:
                    barrier.wait()
                    valid = True
                    with lock:
                        finished.add(name)
                except threading.BrokenBarrierError:
                    valid = False
            self.send_response(200 if valid else 500)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("WORKER_TEST_PORT", str(server.server_port))
    monkeypatch.delenv("CODEBUDDY_OBSERVATION_COMMAND", raising=False)
    monkeypatch.delenv("CODEBUDDY_LOCAL_STATE_COMMAND", raising=False)
    source = pytester.path / "dedicated"
    source.mkdir()
    (source / "config.json").write_text('{"token":"invalid-test-token"}')
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(source))
    pytester.makeconftest('''
def pytest_addoption(parser):
    for name in ("--agent", "--evidence-dir", "--case-suite"):
        parser.addoption(name)
def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: offline fake business test")
    config.addinivalue_line("markers", "smoke: smoke")
    from agent_test_tool import parallel_policy
    parallel_policy.case_execution_policy = lambda path: ("isolated", "offline fixture")
''')
    path = pytester.makepyfile(test_workers='''
import http.client
import json
import os
import pytest

pytestmark = pytest.mark.e2e

def check(name, request):
    conn = http.client.HTTPConnection("127.0.0.1", int(os.environ["WORKER_TEST_PORT"]), timeout=20)
    conn.request("POST", "/", json.dumps({"name":name,"profile":os.environ["CODEBUDDY_CONFIG_DIR"]}))
    response = conn.getresponse()
    assert response.status == 200
    response.read()
    conn.close()
    request.node.user_properties.append(("assessment_status", "通过"))

@pytest.mark.parametrize("index", range(4))
def test_parallel(index, request):
    check(str(index), request)

def test_exclusive(request):
    check("exclusive", request)
''')
    run_directory = pytester.path / "run"
    run_directory.mkdir()

    def process_runner(command, **kwargs):
        result = run_managed_process(command, **kwargs)
        if "--collect-only" in command:
            output = Path(command[command.index("--agent-result-json") + 1])
            payload = json.loads(output.read_text())
            for case in payload["cases"]:
                case["execution_policy"] = "exclusive" if "test_exclusive" in case["nodeid"] else "isolated"
            output.write_text(json.dumps(payload))
        return result

    try:
        execution = run_parallel_business(
            WorkflowConfig(
                agent="codebuddy", output_parent=pytester.path, business_workers=4,
                business_paths=(path,), business_timeout_seconds=40,
            ), "offline-run", run_directory, process_runner,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert execution.returncode == 0, execution.result
    assert execution.result["summary"]["通过"] == 5
    assert execution.result["summary"]["total"] == 5
    assert len(profiles) == 4
    assert str(source) not in profiles
    assert all(not Path(profile).exists() for profile in profiles)
    assert events[-1] == "exclusive"
    assert execution.result["scheduling"]["parallel_count"] == 4
    assert len(list(run_directory.glob("business-worker-*-results.json"))) == 4


def test_collection_failure_does_not_start_any_worker(tmp_path):
    calls = []

    def fail_collection(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 2, "", "collection failure")

    execution = run_parallel_business(
        WorkflowConfig(agent="codebuddy", output_parent=tmp_path, business_workers=4),
        "failed", tmp_path, fail_collection,
    )
    assert execution.returncode == 1
    assert len(calls) == 1
    assert (tmp_path / "business-results.json").is_file()


def test_collection_cleanup_error_still_produces_structured_failure(tmp_path):
    def runner(command, **kwargs):
        raise ProcessCleanupError("simulated collection cleanup error")

    execution = run_parallel_business(
        WorkflowConfig(agent="codebuddy", output_parent=tmp_path, business_workers=4),
        "collection-cleanup", tmp_path, runner,
    )
    assert execution.returncode == 1
    assert execution.result["session"]["exitstatus"] == 1
    assert execution.result["session"]["internal_errors"]
    assert (tmp_path / "business-results.json").is_file()


def _fake_inventory():
    return {
        "session": {"exitstatus": 0, "collected": 5, "reported_cases": 5},
        "cases": [
            {
                "nodeid": f"test_fake.py::test_case[{index}]",
                "test_case_id": f"TC-TEST-{index}", "case_level": "mother",
                "source_case_id": f"TC-TEST-{index}", "status": "通过",
                "pytest_status": "passed",
                "execution_policy": "isolated" if index < 4 else "exclusive",
            }
            for index in range(5)
        ],
    }


def _write_fake_result(command, payload):
    output = Path(command[command.index("--agent-result-json") + 1])
    output.write_text(json.dumps(payload))
    return subprocess.CompletedProcess(command, 0, "", "")


def _selected_payload(command, inventory):
    selection = Path(command[command.index("--agent-nodeids-file") + 1])
    selected = set(json.loads(selection.read_text()))
    records = [case for case in inventory["cases"] if case["nodeid"] in selected]
    return {
        "session": {"exitstatus": 0, "collected": len(records), "reported_cases": len(records)},
        "cases": records,
    }


def test_cleanup_failure_preserves_other_workers_and_blocks_exclusive(tmp_path, monkeypatch):
    inventory = _fake_inventory()
    executed = []
    retained = []

    @contextmanager
    def profile(_product):
        try:
            yield {}
        except ProcessCleanupError:
            retained.append(True)
            raise

    monkeypatch.setattr(AgentModelFactory, "worker_environment", profile)
    monkeypatch.setattr(AgentModelFactory, "parallel_block_reason", lambda product: None)

    def runner(command, **kwargs):
        if "--collect-only" in command:
            return _write_fake_result(command, inventory)
        output = Path(command[command.index("--agent-result-json") + 1]).name
        executed.append(output)
        if output == "business-worker-1-results.json":
            raise ProcessCleanupError("offline simulated cleanup failure")
        return _write_fake_result(command, _selected_payload(command, inventory))

    result = run_parallel_business(
        WorkflowConfig(agent="codebuddy", output_parent=tmp_path, business_workers=4),
        "cleanup-failed", tmp_path, runner,
    )
    assert result.returncode == 1
    assert "business-exclusive-results.json" not in executed
    assert len(retained) == 4
    assert result.result["summary"]["total"] == 5
    assert result.result["summary"]["通过"] == 3
    assert result.result["summary"]["不通过"] == 2
    assert result.result["cases"][0]["test_case_id"] == "TC-TEST-0"


def test_unisolated_helper_forces_serial_without_profile_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEBUDDY_OBSERVATION_COMMAND", "unused-offline-helper")
    inventory = _fake_inventory()
    executed = []

    def unexpected_copy(_product):
        raise AssertionError("Serial fallback must not copy a worker profile")

    monkeypatch.setattr(AgentModelFactory, "worker_environment", unexpected_copy)

    def runner(command, **kwargs):
        if "--collect-only" in command:
            return _write_fake_result(command, inventory)
        executed.append(Path(command[command.index("--agent-result-json") + 1]).name)
        return _write_fake_result(command, _selected_payload(command, inventory))

    result = run_parallel_business(
        WorkflowConfig(agent="codebuddy", output_parent=tmp_path, business_workers=4),
        "helper-serial", tmp_path, runner,
    )
    assert result.returncode == 0
    assert executed == ["business-exclusive-results.json"]
    assert result.result["scheduling"]["parallel_count"] == 0
    assert result.result["scheduling"]["parallel_block_reason"]


@pytest.mark.parametrize("fault", ["timeout", "invalid_json_shape"])
def test_worker_failure_keeps_every_selected_case(tmp_path, monkeypatch, fault):
    inventory = _fake_inventory()

    @contextmanager
    def profile(_product):
        yield {}

    monkeypatch.setattr(AgentModelFactory, "worker_environment", profile)
    monkeypatch.setattr(AgentModelFactory, "parallel_block_reason", lambda product: None)

    def runner(command, **kwargs):
        if "--collect-only" in command:
            return _write_fake_result(command, inventory)
        output = Path(command[command.index("--agent-result-json") + 1]).name
        if output == "business-worker-1-results.json":
            if fault == "timeout":
                raise subprocess.TimeoutExpired(command, 1)
            return _write_fake_result(command, {"session": "invalid", "cases": None})
        return _write_fake_result(command, _selected_payload(command, inventory))

    result = run_parallel_business(
        WorkflowConfig(agent="codebuddy", output_parent=tmp_path, business_workers=4),
        "worker-failed", tmp_path, runner,
    )
    assert result.returncode == 1
    assert result.result["summary"]["total"] == 5
    assert result.result["cases"][0]["status"] == "不通过"
    assert result.result["cases"][0]["source_case_id"] == "TC-TEST-0"
    if fault == "timeout":
        assert result.timed_out
        assert result.result["cases"][4]["status"] == "不通过"


def test_business_deadline_includes_collection(tmp_path, monkeypatch):
    from agent_test_tool import parallel_runner

    now = [0.0]
    monkeypatch.setattr(parallel_runner, "time", SimpleNamespace(monotonic=lambda: now[0]))
    monkeypatch.setattr(AgentModelFactory, "parallel_block_reason", lambda product: "offline serial")
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        now[0] = 2.0
        return _write_fake_result(command, _fake_inventory())

    result = run_parallel_business(
        WorkflowConfig(
            agent="codebuddy", output_parent=tmp_path, business_workers=4,
            business_timeout_seconds=1,
        ), "deadline", tmp_path, runner,
    )
    assert len(calls) == 1
    assert result.timed_out
    assert result.returncode == 1
    assert result.result["summary"]["不通过"] == 5
