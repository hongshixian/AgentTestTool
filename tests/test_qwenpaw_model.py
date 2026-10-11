"""Offline regression for QwenPaw model assembly, installation checks and failure latching."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from agent_models.factory import AgentModelFactory
from agent_models.qwenpaw.client import ApprovalDecision, TurnOutcome, TurnTranscript
from agent_models.qwenpaw.model import QwenPawAgentModel


def _fake_cli(tmp_path: Path, version: str) -> Path:
    script = tmp_path / "qwenpaw"
    script.write_text(f"#!{sys.executable}\nprint('INFO noise')\nprint('QwenPaw, version {version}')\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


@pytest.fixture
def model_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    created: list[QwenPawAgentModel] = []

    def build(version: str | None, *, api_key: str = "sk-test-placeholder") -> QwenPawAgentModel:
        executable = _fake_cli(tmp_path, version) if version else tmp_path / "missing" / "qwenpaw"
        monkeypatch.setenv("QWENPAW_BIN", str(executable))
        monkeypatch.setenv("QWENPAW_TEST_API_KEY", api_key)
        workspace = tmp_path / f"ws{len(created)}"
        workspace.mkdir()
        model = AgentModelFactory.create("qwenpaw", workspace=workspace,
                                         evidence_directory=tmp_path / f"ev{len(created)}")
        assert isinstance(model, QwenPawAgentModel)
        created.append(model)
        return model

    yield build
    for model in created:
        model.close()


@pytest.mark.skipif(os.name == "nt", reason="the fake CLI is a POSIX shebang script")
def test_pinned_version_is_installed(model_factory) -> None:
    result = model_factory("2.2.1").check_installation()
    assert result.installed and "2.2.1" in result.detail


@pytest.mark.skipif(os.name == "nt", reason="the fake CLI is a POSIX shebang script")
def test_other_version_is_not_an_accepted_installation(model_factory) -> None:
    result = model_factory("2.2.2b4").check_installation()
    assert not result.installed and "2.2.1 is required" in result.detail


def test_missing_executable(model_factory) -> None:
    model = model_factory(None)
    assert not model.check_installation().installed
    assert model.check_authentication().status.value == "error"


def test_factory_declares_private_worker_instances() -> None:
    assert AgentModelFactory.parallel_block_reason("qwenpaw") is None
    with AgentModelFactory.worker_environment("qwenpaw") as environment:
        assert environment == {}


def test_api_key_is_redacted_from_evidence(model_factory) -> None:
    model = model_factory(None, api_key="sk-unique-redaction-probe")
    assert "sk-unique-redaction-probe" not in str(model.environment.ledger.redact("key sk-unique-redaction-probe"))


def test_setup_failure_is_latched(model_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    model = model_factory(None)
    model._setup_error = "QwenPaw instance setup failed: simulated"
    with pytest.raises(RuntimeError, match="simulated"):
        model.send_prompt("hello")


def test_turn_result_maps_timeouts_and_stops(model_factory) -> None:
    model = model_factory(None)
    transcript = TurnTranscript()
    transcript.add({"object": "response", "status": "completed"})
    stopped = model._turn_result(TurnOutcome("s", transcript, (), 3.0, timed_out=True, stopped=True))
    assert not stopped.completed and stopped.returncode == -1 and "stop accepted=True" in stopped.stderr
    decision = ApprovalDecision("r", "Bash", "STRICT mode", "ls", False, "not_permitted")
    finished = model._turn_result(TurnOutcome("s", transcript, (decision,), 1.0))
    assert finished.completed and finished.returncode == 0 and "not_permitted" in finished.raw_output
