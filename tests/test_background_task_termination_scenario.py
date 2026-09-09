"""Verify product-managed background task termination assessment paths."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_models import (
    AuthResult,
    AuthStatus,
    BackgroundTaskControlResult,
    BackgroundTaskHandle,
    BackgroundTaskObservation,
    EvidenceAuthority,
    EvidenceCorrelation,
    EvidencePhase,
    EvidenceRecord,
    EvidenceSource,
    EvidenceStatus,
)
from agent_models.capabilities import AgentCapabilities
from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.scenarios.background_task_termination import (
    BackgroundTaskTerminationScenarioRunner,
    TOOL_NAME,
)


class _Runtime:
    def __init__(self) -> None:
        self.released = False

    def wait_for_call(self, name, **_kwargs):
        assert name == TOOL_NAME
        return {"kind": "received"}

    def release_gate(self, _name) -> None:
        self.released = True


class _Ledger:
    def __init__(self) -> None:
        self.events = []

    def record(self, source, kind, data, _correlation_id=None) -> None:
        self.events.append({"source": source, "kind": kind, "data": data})


class _Environment:
    def __init__(self) -> None:
        self.run_id = "unit-run"
        self.runtime = _Runtime()
        self.ledger = _Ledger()
        self.bundles = []

    def archive_bundle(self, bundle) -> None:
        self.bundles.append(bundle)


class _Agent:
    def __init__(
        self,
        *,
        stop_succeeds: bool = True,
        retain_terminal: bool = True,
    ) -> None:
        self.capabilities = AgentCapabilities(
            dedicated_test_account=True,
            background_tasks=True,
            background_task_control=True,
            background_task_inventory_evidence=True,
            multiple_mock_tools=True,
            controlled_environment=True,
        )
        self.environment = _Environment()
        self.stop_succeeds = stop_succeeds
        self.retain_terminal = retain_terminal
        self.stopped = False

    def configure_mock_tools(self, *_args, **_kwargs) -> None:
        return None

    def check_authentication(self) -> AuthResult:
        return AuthResult(AuthStatus.AUTHENTICATED, "unit")

    def start_background_task(self, *_args, **_kwargs) -> BackgroundTaskHandle:
        return BackgroundTaskHandle("task-1", "unit", "session-1")

    def observe_background_tasks(self):
        if self.stopped and not self.retain_terminal:
            return ()
        return (
            BackgroundTaskObservation(
                "task-1",
                "unit",
                "background",
                "stopped" if self.stopped else "working",
                "session-1",
                1,
            ),
        )

    def stop_background_task(self, task_id, **_kwargs) -> BackgroundTaskControlResult:
        assert task_id == "task-1"
        if self.stop_succeeds:
            self.stopped = True
        return BackgroundTaskControlResult(
            task_id,
            self.stop_succeeds,
            0 if self.stop_succeeds else 1,
        )

    def capture_evidence(self, request):
        status = (
            EvidenceStatus.AVAILABLE
            if self.retain_terminal
            else EvidenceStatus.MISSING
        )
        return (
            EvidenceRecord(
                "agent_background_task_state",
                "runtime_evidence",
                EvidencePhase.AFTER,
                {"state": "stopped"} if self.retain_terminal else {},
                status=status,
                source=EvidenceSource(
                    "fixture",
                    "jobs",
                    EvidenceAuthority.PRODUCT_RUNTIME,
                    observed_at="2026-09-09T00:00:00+00:00",
                ),
                correlation=EvidenceCorrelation(
                    run_id="unit-run",
                    session_ids=(request.session_id,),
                    task_ids=(request.task_id,),
                ),
            ),
        )


def _request():
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


def _run(agent: _Agent):
    return BackgroundTaskTerminationScenarioRunner().run_background_external_wait_termination(
        agent,
        _request(),
        sample_id="sample",
        prompt_id="prompt",
    )


class TestBackgroundTaskTerminationScenario:
    def test_explicit_stopped_state_passes(self) -> None:
        agent = _Agent()

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            _run(agent)

        assert outcome.value.verdict.status is AssessmentStatus.PASS
        assert agent.environment.runtime.released
        assert len(agent.environment.bundles) == 1

    def test_rejected_product_stop_fails(self) -> None:
        agent = _Agent(stop_succeeds=False)

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            _run(agent)

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert agent.environment.runtime.released

    def test_missing_product_terminal_state_is_inconclusive(self) -> None:
        agent = _Agent(retain_terminal=False)

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            _run(agent)

        assert outcome.value.verdict.status is AssessmentStatus.INCONCLUSIVE
