"""Verify the unified controlled environment and product facade offline."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from agent_models.environment.session import ControlledEnvironment
from agent_models.environment.ledger import EvidenceLedger
from agent_models.evidence import EvidencePhase, EvidenceRequest
from agent_models.result import TurnResult
from agent_models.tools import ToolDefinition, ToolEffect, ToolResponse, ToolSuite


@pytest.fixture
def environment(tmp_path):
    with ControlledEnvironment(tmp_path / "workspace", evidence_directory=tmp_path / "evidence",
                               secrets=("fake-secret-for-tests",)) as value:
        yield value


def suite():
    return ToolSuite((ToolDefinition("write", "Write simulated value", {"type": "object"},
                     (ToolResponse("ok", effects=(ToolEffect("increment", "count", 1),)),)),),
                     exhaustion="repeat_last")


def test_workspace_tools_restore_without_rewinding_evidence(environment):
    environment.workspace.write_text("input.txt", "original")
    environment.configure_tools(suite(), initial_state={"count": 0})
    snapshot = environment.snapshot()
    environment.runtime.call("write", {})
    environment.workspace.write_text("input.txt", "changed")
    before = len(environment.ledger.events)
    environment.restore(snapshot)
    assert environment.runtime.state == {"count": 0}
    assert environment.workspace.root.joinpath("input.txt").read_text() == "original"
    assert len(environment.ledger.events) > before
    assert environment.health()["healthy"]


def test_restore_and_close_refuse_active_agent_operation(environment):
    snapshot = environment.snapshot()
    with environment.activity("prompt"):
        with pytest.raises(RuntimeError, match="stop Agent"):
            environment.restore(snapshot)
        with pytest.raises(RuntimeError, match="during an Agent"):
            environment.close()
        with pytest.raises(RuntimeError, match="simultaneous"):
            with environment.activity("overlap"):
                pass


def test_checkpoint_from_another_run_is_rejected(environment):
    snapshot = environment.snapshot()
    with pytest.raises(ValueError, match="different environment"):
        environment.restore(replace(snapshot, run_id="unrelated-run"))


def test_environment_runner_repeat_can_restore_environment(environment):
    environment.configure_tools(suite(), initial_state={"count": 0})
    snapshot = environment.snapshot()
    seen = []
    def action(context):
        seen.append(context.run_id)
        environment.runtime.call("write", {})
        return environment.runtime.state["count"]
    assert environment.runner.repeat(3, action, prepare=lambda ctx: None,
        restore=lambda ctx: environment.restore(snapshot)) == [1, 1, 1]
    assert len(set(seen)) == 3


def test_capture_redacts_tool_state_and_archive_persists(environment):
    environment.configure_tools(suite(), initial_state={"value": "fake-secret-for-tests"})
    records = environment.capture(EvidenceRequest("sample", "prompt", 1, EvidencePhase.AFTER))
    assert records[0].data["simulated_state"]["value"] == "[REDACTED]"
    root = environment.evidence_directory
    environment.close()
    assert EvidenceLedger.verify_archive(root)["healthy"]
    assert "fake-secret-for-tests" not in root.joinpath("events.jsonl").read_text()
    assert not list(environment.workspace.root.rglob("*.jsonl"))


def test_reconfiguration_and_post_close_use_fail(environment):
    environment.configure_tools(suite())
    with pytest.raises(RuntimeError, match="once"):
        environment.configure_tools(suite())
    environment.close()
    with pytest.raises(RuntimeError, match="closed"):
        environment.snapshot()


def test_partial_restore_is_reported_unhealthy(environment, monkeypatch):
    snapshot = environment.snapshot()
    def fail(_snapshot):
        raise OSError("test restoration failure")
    monkeypatch.setattr(environment.workspace, "restore", fail)
    with pytest.raises(OSError):
        environment.restore(snapshot)
    assert not environment.health()["healthy"]
    assert "partially restored" in environment.health()["errors"][0]


def test_evidence_cannot_be_nested_in_workspace(tmp_path):
    with pytest.raises(ValueError, match="disjoint"):
        ControlledEnvironment(tmp_path / "workspace", evidence_directory=tmp_path / "workspace" / "evidence")


def make_model(environment, request):
    from agent_models.codebuddy.model import CodeBuddyAgentModel
    from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController
    return CodeBuddyAgentModel(
        workspace=environment.workspace.root,
        environment=environment,
        transport=SimpleNamespace(request=request, close=lambda: None),
        driver=SimpleNamespace(parse_turn=lambda response: response),
        credentials=SimpleNamespace(remove_test_session=lambda _session: None),
        evidence=SimpleNamespace(is_available=lambda: False),
        mock_tool=CodeBuddyMockToolController(workspace=environment.workspace.root, environment=environment),
        local_state=SimpleNamespace(),
    )


def test_model_retains_session_and_full_turns_with_tools_disabled(environment):
    calls = []
    def request(prompt, **kwargs):
        calls.append(kwargs)
        return TurnResult("ok", "x" * 9000 + "fake-secret-for-tests", "", 0, True, 0.01)
    model = make_model(environment, request)
    model.configure_mock_tools(suite(), run_id="scenario", initial_state={"count": 0})
    model.send_prompt("hello", allow_tools=False)
    model.send_prompt("continue")
    assert calls[0]["extra_args"] == ()
    assert calls[1]["extra_args"]
    assert calls[0]["session_id"] == calls[1]["session_id"]
    assert calls[0]["resume"] is False and calls[1]["resume"] is True
    turns = [e for e in environment.ledger.events if e["kind"] == "turn"]
    assert turns[0]["data"]["result"]["raw_output"] == "x" * 9000 + "[REDACTED]"
    with pytest.raises(RuntimeError, match="会话开始前"):
        model.configure_mock_tools(suite(), run_id="later")
    model.close()
    assert EvidenceLedger.verify_archive(environment.evidence_directory)["healthy"]


def test_model_timeout_records_partial_output_and_disallows_reconfiguration(environment):
    def request(_prompt, **_kwargs):
        raise subprocess.TimeoutExpired("fake-cli", 1, output=b"partial", stderr=b"failure")
    model = make_model(environment, request)
    with pytest.raises(subprocess.TimeoutExpired):
        model.send_prompt("test")
    events = environment.ledger.events
    assert next(e for e in events if e["kind"] == "turn_timeout")["data"]["stdout"] == "partial"
    assert events[-1]["kind"] == "operation_failed"
    with pytest.raises(RuntimeError, match="会话开始前"):
        model.configure_mock_tools(suite(), run_id="later")
    model.close()


def test_model_cleanup_attempts_every_component(environment):
    model = make_model(environment, lambda *_a, **_k: None)
    def fail():
        raise RuntimeError("test transport close error")
    model.transport.close = fail
    with pytest.raises(ExceptionGroup, match="cleanup failed"):
        model.close()
    assert environment.ledger.health()["closed"]
    assert EvidenceLedger.verify_archive(environment.evidence_directory)["healthy"]


def test_archive_failure_can_be_retried(environment, monkeypatch):
    original = environment.ledger.close
    def fail():
        raise OSError("temporary finalization failure")
    monkeypatch.setattr(environment.ledger, "close", fail)
    with pytest.raises(ExceptionGroup):
        environment.close()
    monkeypatch.setattr(environment.ledger, "close", original)
    environment.close()
    assert environment.evidence_directory.joinpath("manifest.json").exists()


def test_model_shutdown_blocks_new_operations_before_component_cleanup(environment):
    observed = []
    model = make_model(environment, lambda *_a, **_k: observed.append("unexpected request"))
    def close_transport():
        with pytest.raises(RuntimeError, match="closed"):
            model.send_prompt("racing with shutdown")
        observed.append("closed transport")
    model.transport.close = close_transport
    model.close()
    assert observed == ["closed transport"]
