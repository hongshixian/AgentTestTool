"""Verify mother cases safely delegate to one expanded representative case."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent_models.environment.ledger import EvidenceLedger
from assertions import AssessmentOutcomeSignal, AssessmentStatus, AssessmentVerdict
from test_cases.base import AgentTestCase
from test_cases.mother_cases import base as mother_base
from test_cases.mother_cases.base import MotherCaseScenarioRunner


REPRESENTATIVE_SCRIPT = "test_cases/test_complete_initial_settings_extraction.py"
REPRESENTATIVE_CHILD_ID = "ATS-6.1b-D5-01-S01-01"
SOURCE_CASE_ID = "TC-6.1b-D5-01"


def _synthetic_module(monkeypatch: pytest.MonkeyPatch, test_method: Any) -> None:
    module_name = "test_cases.test_complete_initial_settings_extraction"
    test_class = type(
        "TestSyntheticRepresentative",
        (),
        {
            "__module__": module_name,
            test_method.__name__: test_method,
        },
    )
    module = SimpleNamespace(
        __name__=module_name,
        TEST_CASE_ID=REPRESENTATIVE_CHILD_ID,
        TestSyntheticRepresentative=test_class,
    )
    monkeypatch.setattr(mother_base.importlib, "import_module", lambda _name: module)


def test_resolve_representative_accepts_matching_script_and_id() -> None:
    test_class, test_method = MotherCaseScenarioRunner._resolve_representative(
        REPRESENTATIVE_SCRIPT,
        REPRESENTATIVE_CHILD_ID,
    )

    assert test_class.__name__ == "TestATS61BD501S0101CompleteInitialSettings"
    assert test_method.__name__ == "test_complete_initial_settings_extraction"


def test_resolve_representative_rejects_script_id_mismatch() -> None:
    with pytest.raises(ValueError, match="ID 与脚本不匹配"):
        MotherCaseScenarioRunner._resolve_representative(
            REPRESENTATIVE_SCRIPT,
            "ATS-6.1b-D5-01-S01-NOT-THE-SCRIPT-ID",
        )


@pytest.mark.parametrize(
    "representative_script",
    [
        "../test_cases/test_complete_initial_settings_extraction.py",
        "test_cases/../test_cases/test_complete_initial_settings_extraction.py",
        "/tmp/test_complete_initial_settings_extraction.py",
    ],
)
def test_resolve_representative_rejects_path_escape(
    representative_script: str,
) -> None:
    with pytest.raises(ValueError, match="脚本路径无效"):
        MotherCaseScenarioRunner._resolve_representative(
            representative_script,
            REPRESENTATIVE_CHILD_ID,
        )


def test_run_representative_supplies_all_supported_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def test_supported(
        self: object,
        agent_model: object,
        judge_model: object,
        request: object,
        repeat_index: int,
    ) -> None:
        received.update(
            {
                "instance": self,
                "agent_model": agent_model,
                "judge_model": judge_model,
                "request": request,
                "repeat_index": repeat_index,
            }
        )

    _synthetic_module(monkeypatch, test_supported)
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

    assert received["agent_model"] is agent_model
    assert received["judge_model"] is judge_model
    assert received["request"] is request
    assert received["repeat_index"] == 7


def test_run_representative_rejects_unsupported_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def test_unsupported(self: object, tmp_path: object) -> None:
        raise AssertionError("unsupported representative method must not run")

    _synthetic_module(monkeypatch, test_unsupported)
    ledger = SimpleNamespace(record=lambda *_args: None)
    agent_model = SimpleNamespace(environment=SimpleNamespace(ledger=ledger))
    request = SimpleNamespace(node=SimpleNamespace(user_properties=[]))

    with pytest.raises(RuntimeError, match="不支持的 fixture：tmp_path"):
        MotherCaseScenarioRunner().run_representative_case(
            source_case_id=SOURCE_CASE_ID,
            representative_child_id=REPRESENTATIVE_CHILD_ID,
            representative_script=REPRESENTATIVE_SCRIPT,
            agent_model=agent_model,
            judge_model=None,
            request=request,
            repeat_index=0,
        )


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

    def test_conclusion(
        self: object,
        agent_model: object,
        request: object,
        repeat_index: int,
    ) -> None:
        assert repeat_index == 3
        AgentTestCase()._conclude(request, agent_model, verdict)

    _synthetic_module(monkeypatch, test_conclusion)
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
