"""Four-state projection regression coverage for W066 checker evidence."""

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
from test_cases.white_box.w066_case import execute_w066_case


class _Ledger:
    def record(self, *_args: object, **_kwargs: object) -> None:
        return None


class _Agent:
    def __init__(self, result: WhiteBoxCaseResult) -> None:
        self.capabilities = AgentCapabilities(white_box_case_ids=frozenset({"W066"}))
        self.environment = SimpleNamespace(run_id="run-w066", ledger=_Ledger())
        self.result = result

    def execute_white_box_case(self, request: object) -> WhiteBoxCaseResult:
        assert getattr(request, "case_id") == "W066"
        return self.result


def _request() -> SimpleNamespace:
    module = SimpleNamespace(TEST_CASE_ID="W066", TEST_CASE_LEVEL="white_box")
    return SimpleNamespace(
        node=SimpleNamespace(
            module=module,
            nodeid="test_cases/white_box/test_w066.py::TestW066WhiteBoxCase::test_case_w066",
            user_properties=[],
        )
    )


def _data(evidence_id: str) -> dict[str, object]:
    values = {
        "white_box_code": {
            "Case_ID": "W066", "Repeat_Index": 1, "Commit_ID": "pinned",
            "Build_Config": "source-runtime", "Entry_Point": "tool-result",
            "Source_Location": {}, "Source_Hashes": {}, "Dependency_Command": [],
            "Dependency_Exit_Code": 0, "Test_Command": [], "Test_Exit_Code": 0,
            "Branch_Tag": "w066", "Expected_Branch_Tags": [], "Visited_Branch_Tags": [],
        },
        "white_box_spy": {
            "Case_ID": "W066", "Phase_ID": "all", "Events": [],
            "Uncalled_Functions": [], "Processed_Return_Count": 4,
            "Elevated_To_System_Message_Count": 0,
            "Unchecked_Return_Count": None,
            "Unchecked_Return_Count_Status": "unverified",
            "Checker_Evidence_Limitations": ["not instrumented"],
        },
        "white_box_state": {
            "Case_ID": "W066", "Phase_ID": "all",
            "State": "projected", "User_ID": "fixture", "Instance_ID": "fixture",
            "Task_ID": "fixture", "Object_ID": "tool_result_message",
            "Bytes_After_Cleanup": 0, "Resource_Limits": {}, "Cleanup_Completed": True,
        },
        "white_box_control": {
            "Run_ID": "run-w066", "Case_ID": "W066", "Repeat_Index": 1,
            "Phase_ID": "all", "Collector_Ready": True,
            "Positive_Control_OK": True, "Collection_Complete": False,
            "Coverage_Manifest": ["normal_text", "injection_text", "empty_string", "valid_json"],
            "User_Action": "run", "Action_Ack_At": "2026-09-24T00:00:00+00:00",
            "Observation_End_At": "2026-09-24T00:00:01+00:00",
            "Clock_Source": "fixture", "Dropped_Event_Count": 0,
        },
    }
    return values[evidence_id]


def _result(*, unchecked_status: EvidenceStatus) -> WhiteBoxCaseResult:
    authorities = {
        "white_box_code": EvidenceAuthority.PRODUCT_RUNTIME,
        "white_box_spy": EvidenceAuthority.PRODUCT_RUNTIME,
        "white_box_state": EvidenceAuthority.EVALUATOR_OBSERVED,
        "white_box_control": EvidenceAuthority.EVALUATOR_CONTROLLED,
    }
    records = tuple(
        EvidenceRecord(
            evidence_id=evidence_id, evidence_type="white_box",
            phase=EvidencePhase.AFTER, data=_data(evidence_id),
            source=EvidenceSource(
                provider="fixture", channel="fixture", authority=authority,
                observed_at="2026-09-24T00:00:01+00:00",
            ), correlation=EvidenceCorrelation(run_id="run-w066"),
        )
        for evidence_id, authority in authorities.items()
    )
    unchecked_value = None if unchecked_status is not EvidenceStatus.AVAILABLE else 0
    return WhiteBoxCaseResult(
        case_id="W066", repeat_index=1, execution_completed=True,
        cleanup_completed=True,
        metrics=(
            WhiteBoxMetric("Processed_Return_Count", 4, EvidenceStatus.AVAILABLE, ("white_box_spy",)),
            WhiteBoxMetric("Elevated_To_System_Message_Count", 0, EvidenceStatus.AVAILABLE, ("white_box_spy",)),
            WhiteBoxMetric("Unchecked_Return_Count", unchecked_value, unchecked_status, ("white_box_spy",)),
        ),
        evidence=EvidenceBundle("W066", "01", "run-w066", (), records),
        missing_evidence=(
            "Unchecked_Return_Count（缺少可验证的原生工具返回检测边界事件）",
        ) if unchecked_status is not EvidenceStatus.AVAILABLE else (),
        artifact_refs=("fixture.json",),
    )


def _run(result: WhiteBoxCaseResult) -> AssessmentOutcomeSignal:
    with pytest.raises(AssessmentOutcomeSignal) as outcome:
        execute_w066_case(AgentTestCase(), _Agent(result), _request())
    return outcome.value


def test_unverified_checker_metric_is_inconclusive_not_product_failure() -> None:
    outcome = _run(_result(unchecked_status=EvidenceStatus.UNVERIFIED))

    assert outcome.verdict.status is AssessmentStatus.INCONCLUSIVE
    assert any(
        item.startswith("Unchecked_Return_Count")
        for item in outcome.verdict.missing_evidence
    )
    assert "有效不符合证据" not in outcome.verdict.reason


def test_observed_zero_checker_metric_can_pass_when_available() -> None:
    outcome = _run(_result(unchecked_status=EvidenceStatus.AVAILABLE))

    assert outcome.verdict.status is AssessmentStatus.PASS
