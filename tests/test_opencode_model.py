"""Offline regression coverage for the OpenCode AgentModel integration."""

import json
from pathlib import Path

import pytest

from agent_models import AgentModelFactory, EvidenceRequest
from agent_models.evidence import EvidencePhase
from agent_models.result import TurnResult
from agent_models.tools import ToolDefinition, ToolResponse, ToolSuite


@pytest.fixture
def profile_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    key = tmp_path / "fake-provider-key"
    key.write_text("obviously-invalid-test-secret", encoding="utf-8")
    config = tmp_path / "opencode-source.json"
    config.write_text(json.dumps({
        "provider": {"iiis": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": "https://invalid.example/v1", "apiKey": "{file:" + str(key) + "}"},
            "models": {"infi/deepseek-v4.1-flash": {"name": "Fake"}},
        }},
    }), encoding="utf-8")
    monkeypatch.setenv("OPENCODE_TEST_CONFIG", str(config))
    return config


def test_factory_tracks_real_session_ids_without_provider_access(
    profile_source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sessions: list[str | None] = []
    with AgentModelFactory.create("opencode", workspace=workspace) as model:
        def fake_turn(_prompt, **kwargs):
            sessions.append(kwargs["session_id"])
            return TurnResult(
                "OK", "{}", "", 0, True, 1,
                "ses-test" if len(sessions) <= 2 else "ses-new",
            )
        monkeypatch.setattr(model.driver, "send_prompt", fake_turn)
        assert model.product == "opencode"
        assert model.capabilities.multi_turn
        assert not model.capabilities.reconstructed_agent_trace
        assert model.send_prompt("first").completed
        assert model.send_prompt("second").completed
        model.begin_independent_session()
        assert model.send_prompt("third").completed
        unscoped = model.capture_evidence(EvidenceRequest(
            sample_id="B005", prompt_id="01", repeat_index=1, phase=EvidencePhase.AFTER,
        ))
        assert len(unscoped) == 1
        assert unscoped[0].evidence_id == "opencode_turn_selection"
        assert unscoped[0].status.value == "unverified"
        repeated = model.capture_evidence(EvidenceRequest(
            sample_id="B005", prompt_id="01", repeat_index=1,
            phase=EvidencePhase.AFTER, session_id="ses-test",
        ))
        assert repeated[0].status.value == "unverified"
        records = model.capture_evidence(EvidenceRequest(
            sample_id="B005", prompt_id="01", repeat_index=1,
            phase=EvidencePhase.AFTER, session_id="ses-new",
        ))
        assert {record.evidence_id for record in records} >= {
            "conversation_transcript", "api_cli_runtime_result", "controlled_environment",
        }
        assert all(record.correlation.run_id == model.environment.run_id for record in records)
        assert "obviously-invalid-test-secret" not in (
            model.environment.evidence_directory / "events.jsonl"
        ).read_text(encoding="utf-8")
    assert sessions == [None, "ses-test", None]


def test_factory_connects_mock_mcp_before_first_turn(
    profile_source: Path, tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with AgentModelFactory.create("opencode", workspace=workspace) as model:
        suite = ToolSuite((ToolDefinition(
            "lookup", "Controlled lookup", {"type": "object", "additionalProperties": False},
            (ToolResponse({"ok": True}),),
        ),))
        model.configure_mock_tools(suite, run_id=model.environment.run_id)
        config = json.loads(model.profile.config_file.read_text(encoding="utf-8"))
        assert config["mcp"]["ats_mock"]["type"] == "local"
        assert model.environment.receiver is not None
        assert model.environment.receiver.health()["healthy"]
        records = model.capture_evidence(EvidenceRequest(
            sample_id="B001", prompt_id="01", repeat_index=1, phase=EvidencePhase.AFTER,
        ))
        assert not any(record.evidence_id == "reconstructed_agent_trace" for record in records)


def test_grey_box_factory_uses_run_local_collector_and_metadata_hooks_only(
    profile_source: Path, tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with AgentModelFactory.create(
        "opencode", workspace=workspace,
        test_case_id="test_cases/grey_box/test_h003.py::Test::test_case",
    ) as model:
        assert model.capabilities.network_traffic_evidence
        assert model.capabilities.reconstructed_agent_trace
        assert model.profile.hook_capture is not None
        assert (model.profile.config_file.parent / "plugin/ats_grey_box.js").is_file()
        assert model.profile.process_environment()["ATS_OC_HOOK_CASE_LEVEL"] == "grey_box"
        assert model.profile.process_environment()["HTTPS_PROXY"].startswith("http://127.0.0.1:")
        assert "[REDACTED]" not in model.profile.config_file.read_text(encoding="utf-8")


def test_black_box_factory_never_injects_hooks_or_network_proxy(
    profile_source: Path, tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with AgentModelFactory.create(
        "opencode", workspace=workspace,
        test_case_id="test_cases/black_box/test_b001.py::Test::test_case",
    ) as model:
        assert not model.capabilities.network_traffic_evidence
        assert model.profile.hook_capture is None
        assert not (model.profile.config_file.parent / "plugin").exists()
        assert "ATS_OC_HOOK_CASE_LEVEL" not in model.profile.process_environment()


def test_uncertain_process_cleanup_preserves_profile_and_evidence(
    profile_source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent_models.processes import ProcessCleanupError

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = AgentModelFactory.create("opencode", workspace=workspace)
    original = model.profile.root
    evidence = model.environment.evidence_directory
    def unsafe_child(*_args, **_kwargs):
        raise ProcessCleanupError("test process tree is not stopped")
    monkeypatch.setattr(model.driver, "send_prompt", unsafe_child)
    with pytest.raises(ProcessCleanupError, match="not stopped"):
        model.send_prompt("probe")
    with pytest.raises(ProcessCleanupError, match="preserved"):
        model.close()
    assert original.is_dir() and evidence.is_dir()
    # The fake runner has no surviving process; release the test-only fixture.
    model._cleanup_uncertain = False
    model.close()
    assert not original.exists()


def test_single_mock_tool_requires_pre_prompt_setup_and_redacts_receiver(
    profile_source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent_models.tools import MockToolProfile

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with AgentModelFactory.create("opencode", workspace=workspace) as model:
        profile = MockToolProfile("lookup", "application/json", {"ok": True})
        model.configure_mock_tool(profile, run_id=model.environment.run_id)
        receiver = model.environment.receiver
        assert receiver is not None
        assert receiver.url not in model.environment.ledger.redact(
            {"endpoint": receiver.url}
        )["endpoint"]
        monkeypatch.setattr(
            model.driver, "send_prompt",
            lambda *_args, **_kwargs: TurnResult("OK", "{}", "", 0, True, 1, "ses-tool"),
        )
        assert model.send_prompt("probe").completed
        with pytest.raises(RuntimeError, match="before sending a prompt"):
            model.configure_mock_tool(profile, run_id=model.environment.run_id)
