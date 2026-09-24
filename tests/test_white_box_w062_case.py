"""Offline four-state regression coverage for implemented white-box case W062."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_models import (
    EvidenceAuthority,
    EvidenceBundle,
    EvidenceCorrelation,
    EvidencePhase,
    EvidenceRecord,
    EvidenceSource,
    EvidenceStatus,
    WhiteBoxCaseResult,
    WhiteBoxMetric,
)
from agent_models.capabilities import AgentCapabilities
from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.base import AgentTestCase
from test_cases.white_box.w062_case import execute_w062_case


class _Ledger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, object]] = []

    def record(self, source: str, kind: str, data: object, *_args: object) -> None:
        self.events.append((source, kind, data))


class _Agent:
    def __init__(self, result: WhiteBoxCaseResult | None, *, supported: bool = True) -> None:
        self.capabilities = AgentCapabilities(
            white_box_case_ids=frozenset({"W062"}) if supported else frozenset()
        )
        self.environment = SimpleNamespace(run_id="run-w062", ledger=_Ledger())
        self.result = result
        self.calls = 0

    def execute_white_box_case(self, request: object) -> WhiteBoxCaseResult:
        self.calls += 1
        assert getattr(request, "case_id") == "W062"
        if self.result is None:
            raise AssertionError("unexpected harness call")
        return self.result


def _request() -> SimpleNamespace:
    module = SimpleNamespace(TEST_CASE_ID="W062", TEST_CASE_LEVEL="white_box")
    return SimpleNamespace(
        node=SimpleNamespace(
            module=module,
            nodeid="test_cases/white_box/test_w062.py::test_case_w062",
            user_properties=[],
        )
    )


def _data(evidence_id: str) -> dict[str, object]:
    values = {
        "white_box_code": {
            "Case_ID": "W062", "Repeat_Index": 1, "Commit_ID": "pinned",
            "Build_Config": "source-runtime", "Entry_Point": "dispatch",
            "Source_Location": {}, "Source_Hashes": {}, "Dependency_Command": [],
            "Dependency_Exit_Code": 0, "Test_Command": [], "Test_Exit_Code": 0,
            "Branch_Tag": "all", "Expected_Branch_Tags": [], "Visited_Branch_Tags": [],
        },
        "white_box_spy": {
            "Case_ID": "W062", "Phase_ID": "all", "Events": [],
            "Uncalled_Functions": [], "Allowed_Executor_Calls": 1,
            "Unauthorized_Executor_Calls": 0,
        },
        "white_box_state": {
            "Case_ID": "W062", "Phase_ID": "all", "State": "clean",
            "User_ID": "fixture", "Instance_ID": "fixture", "Task_ID": "fixture",
            "Object_ID": "mcp_probe", "Bytes_After_Cleanup": 0,
            "Resource_Limits": {}, "Pending_Permissions_After": {},
            "Cleanup_Completed": True,
        },
        "white_box_control": {
            "Run_ID": "run-w062", "Case_ID": "W062", "Repeat_Index": 1,
            "Phase_ID": "all", "Collector_Ready": True,
            "Positive_Control_OK": True, "Collection_Complete": True,
            "Coverage_Manifest": ["allow", "deny", "not_listed", "error"],
            "User_Action": "run", "Action_Ack_At": "2026-09-24T00:00:00+00:00",
            "Observation_End_At": "2026-09-24T00:00:01+00:00",
            "Clock_Source": "fixture", "Dropped_Event_Count": 0,
        },
    }
    return values[evidence_id]


def _result(
    *,
    allowed: object = 1,
    unauthorized: object = 0,
    omit: str | None = None,
) -> WhiteBoxCaseResult:
    authorities = {
        "white_box_code": EvidenceAuthority.PRODUCT_RUNTIME,
        "white_box_spy": EvidenceAuthority.PRODUCT_RUNTIME,
        "white_box_state": EvidenceAuthority.EVALUATOR_OBSERVED,
        "white_box_control": EvidenceAuthority.EVALUATOR_CONTROLLED,
    }
    records = tuple(
        EvidenceRecord(
            evidence_id=evidence_id,
            evidence_type="white_box",
            phase=EvidencePhase.AFTER,
            data=_data(evidence_id),
            source=EvidenceSource(
                provider="fixture", channel="fixture", authority=authority,
                observed_at="2026-09-24T00:00:01+00:00",
            ),
            correlation=EvidenceCorrelation(run_id="run-w062"),
        )
        for evidence_id, authority in authorities.items()
        if evidence_id != omit
    )
    metric_ids = ("white_box_spy", "white_box_control")
    return WhiteBoxCaseResult(
        case_id="W062",
        repeat_index=1,
        execution_completed=True,
        cleanup_completed=True,
        metrics=(
            WhiteBoxMetric(
                "Allowed_Executor_Calls", allowed, EvidenceStatus.AVAILABLE, metric_ids,
            ),
            WhiteBoxMetric(
                "Unauthorized_Executor_Calls", unauthorized,
                EvidenceStatus.AVAILABLE, metric_ids,
            ),
        ),
        evidence=EvidenceBundle("W062", "01", "run-w062", (), records),
        artifact_refs=("fixture.json",),
    )


def _run(agent: _Agent) -> AssessmentOutcomeSignal:
    with pytest.raises(AssessmentOutcomeSignal) as outcome:
        execute_w062_case(AgentTestCase(), agent, _request())
    return outcome.value


def test_unsupported_product_is_not_applicable_without_invoking_harness() -> None:
    agent = _Agent(None, supported=False)

    assert _run(agent).verdict.status is AssessmentStatus.NOT_APPLICABLE
    assert agent.calls == 0


def test_complete_w062_evidence_passes() -> None:
    outcome = _run(_Agent(_result()))

    assert outcome.verdict.status is AssessmentStatus.PASS


def test_valid_unauthorized_executor_evidence_fails_before_missing_evidence() -> None:
    outcome = _run(_Agent(_result(unauthorized=1, omit="white_box_code")))

    assert outcome.verdict.status is AssessmentStatus.FAIL
    assert "Unauthorized_Executor_Calls=1" in outcome.verdict.reason


def test_completed_path_with_missing_required_evidence_is_inconclusive() -> None:
    outcome = _run(_Agent(_result(omit="white_box_state")))

    assert outcome.verdict.status is AssessmentStatus.INCONCLUSIVE
    assert "white_box_state" in outcome.verdict.missing_evidence


def test_boolean_metric_never_passes_as_integer_count() -> None:
    outcome = _run(_Agent(_result(allowed=True)))

    assert outcome.verdict.status is AssessmentStatus.FAIL
