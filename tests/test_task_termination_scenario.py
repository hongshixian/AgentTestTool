"""Verify executable task-termination paths use the public runtime control."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_models import (
    AgentEvent,
    AgentEventType,
    AuthResult,
    AuthStatus,
    ControlResult,
    EvidenceAuthority,
    EvidenceCorrelation,
    EvidencePhase,
    EvidenceRecord,
    EvidenceSource,
    TurnHandle,
    TurnResult,
)
from agent_models.capabilities import AgentCapabilities
from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.scenarios.task_termination_stage_boundaries import (
    FOREGROUND_VARIANTS,
    VARIANTS,
    TaskTerminationBoundaryScenarioRunner,
)


class _Ledger:
    def __init__(self) -> None:
        self.events = []

    def record(self, source, kind, data) -> None:
        self.events.append((source, kind, data))


class _Environment:
    def __init__(self) -> None:
        self.run_id = "unit-run"
        self.ledger = _Ledger()
        self.bundles = []
        self.runtime = None

    def archive_bundle(self, bundle) -> None:
        self.bundles.append(bundle)


class _Session:
    def __init__(self, *, interrupt_succeeds: bool = True) -> None:
        self.session_id = "requested-session-1"
        self.interrupt_succeeds = interrupt_succeeds
        self.interrupted = False
        self.closed = False
        self.handle = TurnHandle("turn-1", "prompt", 0, 1.0)

    def send_input(self, prompt: str) -> TurnHandle:
        self.handle = TurnHandle("turn-1", prompt, 0, 1.0)
        return self.handle

    def wait_for_event(self, event_types, **_kwargs) -> AgentEvent:
        assert AgentEventType.THINKING in event_types
        return AgentEvent(
            1,
            AgentEventType.THINKING,
            "2026-09-09T00:00:00+00:00",
            1.0,
            session_id="session-1",
            turn_id="turn-1",
            text="planning",
        )

    def interrupt_task(self, **_kwargs) -> ControlResult:
        self.interrupted = True
        return ControlResult(
            "interrupt-1",
            self.interrupt_succeeds,
            {"interrupted": self.interrupt_succeeds},
            "rejected" if not self.interrupt_succeeds else "",
        )

    def wait_for_completion(self, _turn, **_kwargs) -> TurnResult:
        return TurnResult(
            "",
            '{"type":"result","subtype":"error_during_execution"}',
            "interrupted",
            0,
            False,
            0.1,
            "session-1",
        )

    def close(self) -> None:
        self.closed = True


class _Agent:
    def __init__(self, *, interrupt_succeeds: bool = True) -> None:
        self.capabilities = AgentCapabilities(
            dedicated_test_account=True,
            interactive_session=True,
            streaming_events=True,
            runtime_control=True,
        )
        self.environment = _Environment()
        self.session = _Session(interrupt_succeeds=interrupt_succeeds)
        self.started = False

    def check_authentication(self) -> AuthResult:
        return AuthResult(AuthStatus.AUTHENTICATED, "unit")

    def start_session(self, **_kwargs):
        self.started = True
        return self.session

    def capture_evidence(self, request):
        source = EvidenceSource(
            "fixture",
            "stream",
            EvidenceAuthority.PRODUCT_RUNTIME,
            observed_at="2026-09-09T00:00:01+00:00",
        )
        correlation = EvidenceCorrelation(
            run_id="unit-run",
            session_ids=(request.session_id,),
            turn_ids=("turn-1",),
        )
        return tuple(
            EvidenceRecord(
                evidence_id,
                "runtime_evidence",
                EvidencePhase.AFTER,
                {},
                source=source,
                correlation=correlation,
            )
            for evidence_id in ("agent_runtime_stream", "agent_runtime_control")
        )


def _request():
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


class TestTaskTerminationScenario:
    def test_observable_planning_boundary_executes_before_inconclusive(self) -> None:
        agent = _Agent()

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            TaskTerminationBoundaryScenarioRunner().run_foreground_termination_entry(
                agent,
                _request(),
                FOREGROUND_VARIANTS["ATS-7.2c-D1-02-S01-01"],
            )

        assert outcome.value.verdict.status is AssessmentStatus.INCONCLUSIVE
        assert agent.started
        assert agent.session.interrupted
        assert agent.session.closed
        assert len(agent.environment.bundles) == 1

    def test_rejected_native_interrupt_is_a_failed_assessment(self) -> None:
        agent = _Agent(interrupt_succeeds=False)

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            TaskTerminationBoundaryScenarioRunner().run_foreground_termination_entry(
                agent,
                _request(),
                FOREGROUND_VARIANTS["ATS-7.2c-D1-02-S01-01"],
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert agent.session.closed

    def test_unobservable_queue_boundary_remains_not_applicable(self) -> None:
        agent = _Agent()

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            TaskTerminationBoundaryScenarioRunner().run_task_termination_boundary(
                agent,
                _request(),
                VARIANTS["ATS-7.2c-D4-01-S01-01"],
            )

        assert outcome.value.verdict.status is AssessmentStatus.NOT_APPLICABLE
        assert not agent.started
