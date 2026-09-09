"""Verify factory, STDIO bridge, state restoration and evidence with a local CLI probe."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from agent_models import (
    AgentModelFactory,
    EvidenceBundle,
    EvidencePhase,
    EvidenceRequest,
    PermissionPolicy,
    ToolDefinition,
    ToolEffect,
    ToolResponse,
    ToolSuite,
    TranscriptTurn,
)
from agent_models.environment import EvidenceLedger
from assertions.environment import assert_tool_call_count, assert_simulated_effect


def test_factory_to_stdio_tools_and_archive_across_independent_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path / "test-account"))
    monkeypatch.setenv("JUDGE_API_KEY", "fake-judge-secret-not-valid")
    monkeypatch.delenv("CODEBUDDY_OBSERVATION_COMMAND", raising=False)
    monkeypatch.delenv("CODEBUDDY_LOCAL_STATE_COMMAND", raising=False)
    original_run = subprocess.run
    probe = Path(__file__).resolve().parents[1] / "assets" / "framework_fixtures" / "cli_protocol_probe.py"
    launches = []
    def run_local_probe(command, **kwargs):
        assert command[0] == "codebuddy", "this test must never launch a real product"
        assert "JUDGE_API_KEY" not in kwargs["env"]
        launches.append(command)
        return original_run([sys.executable, str(probe), *command[1:]], **kwargs)
    monkeypatch.setattr(subprocess, "run", run_local_probe)
    suite = ToolSuite((
        ToolDefinition("read", "Read simulated content", {"type": "object"},
                       (ToolResponse("baseline"), ToolResponse("injected content"))),
        ToolDefinition("write", "Write simulated data", {"type": "object"},
                       (ToolResponse("ok", effects=(ToolEffect("increment", "writes", 1),)),))),
                       exhaustion="repeat_last")
    run_ids, session_ids = [], []
    for index in range(3):
        evidence_directory = tmp_path / f"evidence-{index}"
        with AgentModelFactory.create("codebuddy", workspace=tmp_path / "workspace",
                                       evidence_directory=evidence_directory) as model:
            env = model.environment
            run_ids.append(env.run_id)
            env.workspace.write_text("input.txt", "baseline")
            model.configure_mock_tools(suite, run_id=env.run_id, initial_state={"writes": 0})
            snapshot = env.snapshot()
            transcript = []
            for name in ("read", "read", "write"):
                prompt = json.dumps({"name": name, "arguments": {}})
                result = model.send_prompt(prompt, timeout=10)
                assert result.completed
                transcript.append(TranscriptTurn(prompt, result))
            assert "baseline" in transcript[0].result.response
            assert "injected content" in transcript[1].result.response
            assert len({turn.result.session_id for turn in transcript}) == 1
            session_ids.append(transcript[0].result.session_id)
            assert_tool_call_count(env.ledger, "read", 2)
            assert_simulated_effect(env.ledger, "write", "writes", 0, 1)
            records = model.capture_evidence(EvidenceRequest("fixture", "wiring", 1, EvidencePhase.AFTER))
            assert len(list(evidence_directory.glob("capture_*.json"))) == 1
            assert len(next(r for r in records if r.evidence_id == "mock_tool_io").data["calls"]) == 3
            bundle = EvidenceBundle("fixture", "wiring", env.run_id, tuple(transcript), records)
            env.archive_bundle(bundle)
            assert "controlled_environment" in bundle.available_evidence_ids
            assert bundle.judge_payload()["external_evidence"]
            env.workspace.write_text("input.txt", "changed")
            env.restore(snapshot)
            assert env.runtime.state == {"writes": 0}
            assert env.workspace.root.joinpath("input.txt").read_text() == "baseline"
        assert EvidenceLedger.verify_archive(evidence_directory)["healthy"]
    assert len(set(run_ids)) == len(set(session_ids)) == 3
    assert len(launches) == 9


def test_model_prompt_and_controlled_gate_synchronize_through_public_api(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path / "test-account"))
    monkeypatch.delenv("CODEBUDDY_OBSERVATION_COMMAND", raising=False)
    monkeypatch.delenv("CODEBUDDY_LOCAL_STATE_COMMAND", raising=False)
    original_run = subprocess.run
    probe = Path(__file__).resolve().parents[1] / "assets" / "framework_fixtures" / "cli_protocol_probe.py"
    def run_local(command, **kwargs):
        assert command[0] == "codebuddy"
        return original_run([sys.executable, str(probe), *command[1:]], **kwargs)
    monkeypatch.setattr(subprocess, "run", run_local)
    suite = ToolSuite((ToolDefinition("submit", "Simulated delayed submission", {"type": "object"},
        (ToolResponse("ok", gate="release", effects=(ToolEffect("set", "submitted", True),)),)),))
    with AgentModelFactory.create("codebuddy", workspace=tmp_path / "workspace",
                                   evidence_directory=tmp_path / "evidence") as model:
        env = model.environment
        model.configure_mock_tools(suite, run_id=env.run_id, initial_state={"submitted": False})
        def release(context):
            received = env.runtime.wait_for_call("submit", timeout=5)
            context.checkpoint()
            assert env.runtime.state == {"submitted": False}
            env.runtime.release_gate("release")
            return received["correlation_id"]
        results = env.runner.parallel({
            "prompt": lambda ctx: model.send_prompt(json.dumps({"name": "submit", "arguments": {}}), timeout=10),
            "release": release,
        }, timeout=12)
        assert results["prompt"].completed
        assert_simulated_effect(env.ledger, "submit", "submitted", False, True,
                                correlation_id=results["release"])


def test_factory_interactive_session_archives_standard_runtime_evidence(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path / "test-account"))
    monkeypatch.setenv("JUDGE_API_KEY", "fake-judge-secret-not-valid")
    monkeypatch.delenv("CODEBUDDY_OBSERVATION_COMMAND", raising=False)
    monkeypatch.delenv("CODEBUDDY_LOCAL_STATE_COMMAND", raising=False)
    original_popen = subprocess.Popen
    probe = (
        Path(__file__).resolve().parents[1]
        / "assets"
        / "framework_fixtures"
        / "interactive_cli_protocol_probe.py"
    )
    launches = []

    def popen_local(command, **kwargs):
        assert command[0] == "codebuddy", "this test must never launch a real product"
        assert "JUDGE_API_KEY" not in kwargs["env"]
        launches.append(tuple(command))
        return original_popen([sys.executable, "-u", str(probe)], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", popen_local)
    evidence_directory = tmp_path / "interactive-evidence"
    with AgentModelFactory.create(
        "codebuddy",
        workspace=tmp_path / "workspace",
        evidence_directory=evidence_directory,
    ) as model:
        session = model.start_session(
            allow_tools=False,
            permission_policy=PermissionPolicy.ASK,
        )
        with pytest.raises(RuntimeError, match="stop Agent"):
            model.environment.snapshot()
        first = session.send_input("one")
        first_result = session.wait_for_completion(first)
        second = session.send_input("two")
        second_result = session.wait_for_completion(second)
        session.close()

        records = model.capture_evidence(
            EvidenceRequest(
                "fixture",
                "interactive",
                1,
                EvidencePhase.AFTER,
                session_id=first_result.session_id,
            )
        )
        available = {record.evidence_id for record in records if record.available}
        assert first_result.completed and second_result.completed
        assert "agent_runtime_stream" in available
        assert "agent_session_correlation" in available
        runtime = next(
            record for record in records if record.evidence_id == "agent_runtime_stream"
        )
        assert runtime.correlation.run_id == model.environment.run_id
        assert len(runtime.correlation.turn_ids) == 2
        assert runtime.source is not None
        assert runtime.source.channel == "stdio_stream_json"
    assert len(launches) == 1
    assert EvidenceLedger.verify_archive(evidence_directory)["healthy"]


def test_model_starts_two_sequential_independent_interactive_sessions(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path / "test-account"))
    monkeypatch.delenv("CODEBUDDY_OBSERVATION_COMMAND", raising=False)
    monkeypatch.delenv("CODEBUDDY_LOCAL_STATE_COMMAND", raising=False)
    original_popen = subprocess.Popen
    probe = (
        Path(__file__).resolve().parents[1]
        / "assets"
        / "framework_fixtures"
        / "interactive_cli_protocol_probe.py"
    )

    def popen_local(command, **kwargs):
        assert command[0] == "codebuddy"
        return original_popen([sys.executable, "-u", str(probe)], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", popen_local)
    with AgentModelFactory.create(
        "codebuddy",
        workspace=tmp_path / "workspace",
        evidence_directory=tmp_path / "evidence",
    ) as model:
        first = model.start_session(allow_tools=False)
        first_result = first.run_turn("first", timeout=2)
        first_requested_id = first.session_id
        with pytest.raises(RuntimeError, match="先关闭"):
            model.start_session(allow_tools=False)
        first.close()

        second = model.start_session(allow_tools=False)
        second_result = second.run_turn("second", timeout=2)
        second_requested_id = second.session_id
        second.close()

        assert first_result.completed and second_result.completed
        assert first_requested_id != second_requested_id
        assert model.capabilities.independent_sessions
