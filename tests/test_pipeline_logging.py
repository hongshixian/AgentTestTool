"""Verify the normalized per-case pipeline event protocol."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_models.environment.ledger import EvidenceLedger
from assertions.outcome import AssessmentOutcomeSignal, AssessmentStatus, assessment_verdict
from test_cases.pipeline import (
    PIPELINE_SOURCE,
    PipelinePhase,
    pipeline_phase,
    record_case_event,
    record_conclusion,
)


def _context(tmp_path: Path):
    ledger = EvidenceLedger(tmp_path / "evidence", run_id="pipeline-run")
    model = SimpleNamespace(environment=SimpleNamespace(ledger=ledger))
    module = SimpleNamespace(TEST_CASE_ID="W001", TEST_CASE_LEVEL="white_box")
    request = SimpleNamespace(node=SimpleNamespace(nodeid="node", module=module))
    return request, model, ledger


def test_pipeline_phase_records_correlated_start_and_completion(tmp_path: Path) -> None:
    request, model, ledger = _context(tmp_path)

    record_case_event(request, model, "case_started")
    with pipeline_phase(request, model, PipelinePhase.INITIALIZE):
        pass

    events = [event for event in ledger.events if event["source"] == PIPELINE_SOURCE]
    assert [event["kind"] for event in events] == [
        "case_started",
        "phase_started",
        "phase_completed",
    ]
    assert events[1]["correlation_id"] == events[2]["correlation_id"]
    assert events[2]["data"]["case_id"] == "W001"
    assert events[2]["data"]["case_level"] == "white_box"
    assert events[2]["data"]["phase"] == "initialize"
    assert events[2]["data"]["duration_seconds"] >= 0


def test_not_applicable_phase_and_conclusion_use_the_same_protocol(tmp_path: Path) -> None:
    request, model, ledger = _context(tmp_path)
    verdict = assessment_verdict(
        AssessmentStatus.NOT_APPLICABLE,
        reason="当前暂未实现：缺少白盒源码",
    )

    with pytest.raises(AssessmentOutcomeSignal):
        with pipeline_phase(request, model, PipelinePhase.CAPABILITY_CHECK):
            raise AssessmentOutcomeSignal(verdict)

    events = [event for event in ledger.events if event["source"] == PIPELINE_SOURCE]
    assert any(
        event["kind"] == "phase_not_applicable"
        and event["data"]["phase"] == "capability_check"
        and event["data"]["status"] == "不适用"
        for event in events
    )
    completed = [event for event in events if event["kind"] == "case_completed"]
    assert completed[0]["data"]["status"] == "不适用"
