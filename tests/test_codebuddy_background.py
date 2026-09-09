"""Verify CodeBuddy public background task control and evidence adapters."""

from __future__ import annotations

import json
import subprocess

import pytest

from agent_models import (
    AgentModelFactory,
    EvidencePhase,
    EvidenceRequest,
    PermissionPolicy,
)


class TestCodeBuddyBackgroundTasks:
    def test_public_lifecycle_produces_correlated_runtime_evidence(
        self,
        tmp_path,
        monkeypatch,
    ) -> None:
        monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path / "account"))
        monkeypatch.setenv("JUDGE_API_KEY", "fake-secret-not-valid")
        monkeypatch.delenv("CODEBUDDY_OBSERVATION_COMMAND", raising=False)
        monkeypatch.delenv("CODEBUDDY_LOCAL_STATE_COMMAND", raising=False)
        calls = []
        state = {"value": "working"}

        def run(command, **kwargs):
            calls.append((tuple(command), kwargs))
            assert command[0] == "codebuddy"
            assert "JUDGE_API_KEY" not in kwargs["env"]
            if "--bg" in command:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    "backgrounded · task-123 · ats-test (agent task)\n",
                    "",
                )
            if command[1:4] == ["agents", "--jobs", "--all"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    json.dumps(
                        [
                            {
                                "id": "task-123",
                                "name": "ats-test",
                                "kind": "background",
                                "sessionId": "session-123",
                                "startedAt": 123456,
                                "state": state["value"],
                            }
                        ]
                    ),
                    "",
                )
            if command[1:3] == ["logs", "task-123"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    "product runtime log",
                    "",
                )
            if command[1:3] == ["stop", "task-123"]:
                state["value"] = "stopped"
                return subprocess.CompletedProcess(command, 0, "stopped", "")
            raise AssertionError(f"unexpected command: {command}")

        monkeypatch.setattr(subprocess, "run", run)
        with AgentModelFactory.create(
            "codebuddy",
            workspace=tmp_path / "workspace",
            evidence_directory=tmp_path / "evidence",
            run_id="run-background",
        ) as model:
            assert model.capabilities.background_tasks
            assert model.capabilities.background_task_control
            assert model.capabilities.background_task_inventory_evidence
            assert model.capabilities.background_task_log_evidence

            handle = model.start_background_task(
                "perform a deterministic test task",
                name="ats-test",
                allow_tools=False,
                permission_policy=PermissionPolicy.DENY_UNAPPROVED,
            )
            observations = model.observe_background_tasks()
            logs = model.read_background_task_logs(handle.task_id)
            records = model.capture_evidence(
                EvidenceRequest(
                    "sample",
                    "prompt",
                    1,
                    EvidencePhase.AFTER,
                    session_id=handle.session_id,
                    task_id=handle.task_id,
                )
            )
            stopped = model.stop_background_task(handle.task_id)

            assert handle.task_id == "task-123"
            assert handle.session_id == "session-123"
            assert observations[0].state == "working"
            assert logs == "product runtime log"
            assert stopped.success
            by_id = {record.evidence_id: record for record in records}
            assert by_id["agent_background_task_state"].available
            assert by_id["agent_background_task_log"].available
            assert by_id["agent_background_task_state"].correlation.task_ids == (
                "task-123",
            )
            assert by_id["agent_background_task_state"].correlation.session_ids == (
                "session-123",
            )

        launch = next(command for command, _kwargs in calls if "--bg" in command)
        assert launch[-1] == "perform a deterministic test task"
        assert "--permission-mode" in launch
        assert ("codebuddy", "stop", "task-123") in {
            command for command, _kwargs in calls
        }

    def test_invalid_inventory_fails_closed(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path / "account"))

        def run(command, **_kwargs):
            return subprocess.CompletedProcess(command, 0, "not-json", "")

        monkeypatch.setattr(subprocess, "run", run)
        with AgentModelFactory.create(
            "codebuddy",
            workspace=tmp_path / "workspace",
        ) as model:
            with pytest.raises(RuntimeError, match="invalid JSON"):
                model.observe_background_tasks()
