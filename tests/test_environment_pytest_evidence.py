"""Verify pytest evidence lifecycle without invoking a real Agent."""

import json
from types import SimpleNamespace

import pytest

from agent_models.environment import EvidenceLedger
from test_cases.conftest import agent_model, pytest_runtest_makereport


def test_fixture_creates_independent_archives_and_captures_phase_results(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path / "account"))
    monkeypatch.setenv("JUDGE_API_KEY", "fake-secret-for-fixture")
    monkeypatch.delenv("CODEBUDDY_OBSERVATION_COMMAND", raising=False)
    monkeypatch.delenv("CODEBUDDY_LOCAL_STATE_COMMAND", raising=False)
    ids = []
    for _ in range(2):
        node = SimpleNamespace(nodeid="offline-fixture-probe", stash=pytest.Stash(), user_properties=[])
        config = SimpleNamespace(getoption=lambda name: {
            "--agent": "codebuddy", "--evidence-dir": str(tmp_path / "evidence")}[name])
        request = SimpleNamespace(node=node, config=config)
        fixture = agent_model.__wrapped__(request, tmp_path / "workspace")
        model = next(fixture)
        ids.append(model.environment.run_id)
        model.environment.ledger.record("test", "redaction", {"text": "fake-secret-for-fixture"})
        hook = pytest_runtest_makereport(node, None)
        next(hook)
        with pytest.raises(StopIteration):
            hook.send(SimpleNamespace(get_result=lambda: SimpleNamespace(when="call", outcome="failed", duration=0.1)))
        with pytest.raises(StopIteration):
            next(fixture)
        directory = model.environment.evidence_directory
        assert EvidenceLedger.verify_archive(directory)["healthy"]
        artifact = json.loads((directory / "pytest_outcome.json").read_text())
        assert artifact["phases"]["call"]["outcome"] == "failed"
        assert "fake-secret-for-fixture" not in (directory / "events.jsonl").read_text()
        assert node.user_properties == [("evidence_directory", str(directory))]
    assert len(set(ids)) == 2
