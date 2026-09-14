"""Verify mother cases execute one retained representative scenario."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_models.environment.ledger import EvidenceLedger
from assertions import AssessmentOutcomeSignal, AssessmentStatus, AssessmentVerdict
from test_cases.base import AgentTestCase
from test_cases.mother_cases import base as mother_base
from test_cases.mother_cases.base import MotherCaseScenarioRunner


REPRESENTATIVE_SCRIPT = "test_cases/test_complete_initial_settings_extraction.py"
REPRESENTATIVE_CHILD_ID = "ATS-6.1b-D5-01-S01-01"
SOURCE_CASE_ID = "TC-6.1b-D5-01"


def test_resolve_representative_accepts_registered_path() -> None:
    runner = MotherCaseScenarioRunner._resolve_representative(
        REPRESENTATIVE_CHILD_ID,
        REPRESENTATIVE_SCRIPT,
    )

    assert callable(runner)


def test_resolve_representative_rejects_legacy_script_mismatch() -> None:
    with pytest.raises(ValueError, match="ID 与历史脚本不匹配"):
        MotherCaseScenarioRunner._resolve_representative(
            REPRESENTATIVE_CHILD_ID,
            "test_cases/test_not_the_selected_child.py",
        )


def test_resolve_representative_rejects_unregistered_id() -> None:
    with pytest.raises(ValueError, match="代表路径未注册"):
        MotherCaseScenarioRunner._resolve_representative(
            "ATS-UNKNOWN",
            REPRESENTATIVE_SCRIPT,
        )


def test_run_representative_supplies_standard_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def representative(
        agent_model: object,
        judge_model: object,
        request: object,
        repeat_index: int,
    ) -> None:
        received.update(
            {
                "agent_model": agent_model,
                "judge_model": judge_model,
                "request": request,
                "repeat_index": repeat_index,
            }
        )

    monkeypatch.setattr(
        mother_base,
        "resolve_representative_path",
        lambda _case_id, _script: representative,
    )
    ledger = SimpleNamespace(record=lambda *_args: None)
    agent_model = SimpleNamespace(environment=SimpleNamespace(ledger=ledger))
    judge_model = object()
    request = SimpleNamespace(node=SimpleNamespace(user_properties=[]))

    MotherCaseScenarioRunner().run_representative_case(
        source_case_id=SOURCE_CASE_ID,
        representative_child_id=REPRESENTATIVE_CHILD_ID,
        representative_script=REPRESENTATIVE_SCRIPT,
        agent_model=agent_model,
        judge_model=judge_model,
        request=request,
        repeat_index=7,
    )

    assert received == {
        "agent_model": agent_model,
        "judge_model": judge_model,
        "request": request,
        "repeat_index": 7,
    }


@pytest.mark.parametrize("status", list(AssessmentStatus))
def test_run_representative_records_linkage_and_propagates_four_state_signal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: AssessmentStatus,
) -> None:
    verdict = AssessmentVerdict(
        status=status,
        reason=f"synthetic {status.value} verdict",
        missing_evidence=("synthetic missing evidence",)
        if status is AssessmentStatus.INCONCLUSIVE
        else (),
    )

    def representative(
        agent_model: object,
        _judge_model: object,
        request: object,
        repeat_index: int,
    ) -> None:
        assert repeat_index == 3
        AgentTestCase()._conclude(request, agent_model, verdict)

    monkeypatch.setattr(
        mother_base,
        "resolve_representative_path",
        lambda _case_id, _script: representative,
    )
    ledger = EvidenceLedger(tmp_path / "evidence", run_id="mother-run")
    agent_model = SimpleNamespace(environment=SimpleNamespace(ledger=ledger))
    request = SimpleNamespace(node=SimpleNamespace(user_properties=[]))

    with pytest.raises(AssessmentOutcomeSignal) as outcome:
        MotherCaseScenarioRunner().run_representative_case(
            source_case_id=SOURCE_CASE_ID,
            representative_child_id=REPRESENTATIVE_CHILD_ID,
            representative_script=REPRESENTATIVE_SCRIPT,
            agent_model=agent_model,
            judge_model=None,
            request=request,
            repeat_index=3,
        )

    assert outcome.value.verdict is verdict
    assert [(event["source"], event["kind"]) for event in ledger.events] == [
        ("pytest", "mother_case_representative_started"),
        ("assertion", "assessment_concluded"),
    ]
    assert ledger.events[0]["data"] == {
        "source_case_id": SOURCE_CASE_ID,
        "representative_child_id": REPRESENTATIVE_CHILD_ID,
        "representative_script": REPRESENTATIVE_SCRIPT,
    }
    assert ledger.events[1]["data"]["status"] == status.value
    assert ledger.close()["healthy"]
