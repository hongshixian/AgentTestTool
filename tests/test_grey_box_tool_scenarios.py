"""Regression tests for deterministic grey-box controlled-tool scenarios."""

from __future__ import annotations

import pytest

from agent_models import EvidenceBundle, EvidencePhase, EvidenceRecord, TranscriptTurn, TurnResult
from assertions.judge import JudgeStatus
from test_cases.grey_box.specs import load_grey_box_specs
from test_cases.grey_box.tool_scenarios import (
    TOOL_SCENARIO_CASE_IDS,
    configure,
    evaluate,
    prepare,
    prompt,
)


def _turn() -> TurnResult:
    return TurnResult("done", "ignored protocol output", "", 0, True, 0.1, "session")


def _call(expected, index: int) -> dict:
    body = expected.response_body
    return {
        "tool_name": expected.tool_name,
        "arguments": dict(expected.arguments),
        "content_type": "application/json",
        "body": body,
        "result": {
            "content": [{"type": "text", "text": str(body)}],
            "structuredContent": body if isinstance(body, dict) else None,
            "isError": expected.is_error,
        },
        "correlation_id": f"call-{index}",
        "call_index": index,
    }


def _bundle(case_id: str, calls: list[dict] | None) -> EvidenceBundle:
    records = () if calls is None else (
        EvidenceRecord(
            "mock_tool_io",
            "runtime_evidence",
            EvidencePhase.AFTER,
            {"tool_names": sorted({call["tool_name"] for call in calls}), "calls": calls},
        ),
    )
    return EvidenceBundle(case_id, "01", "run", (TranscriptTurn("prompt", _turn()),), records)


def test_catalog_and_plan_cover_every_assigned_tool_case() -> None:
    specs = load_grey_box_specs()
    assert len(TOOL_SCENARIO_CASE_IDS) == 36
    for case_id in TOOL_SCENARIO_CASE_IDS:
        plan = prepare(specs[case_id])
        assert plan.case_id == case_id
        assert plan.expected_calls
        assert {definition.name for definition in plan.suite.definitions} >= {
            call.tool_name for call in plan.expected_calls
        }
        assert "PROBE" not in prompt(plan)
        assert "受控的真实语义工具" in prompt(plan)


def test_prepare_rejects_non_tool_case() -> None:
    with pytest.raises(KeyError, match="not a controlled-tool scenario"):
        prepare(load_grey_box_specs()["H003"])


@pytest.mark.parametrize("case_id", sorted(TOOL_SCENARIO_CASE_IDS))
def test_complete_semantic_calls_pass_or_report_unprovable_dimension(case_id: str) -> None:
    plan = prepare(load_grey_box_specs()[case_id])
    calls = [_call(expected, index) for index, expected in enumerate(plan.expected_calls, 1)]
    verdict = evaluate(plan, _bundle(case_id, calls), _turn())
    expected_insufficient = bool(plan.required_dimensions)
    assert (verdict.status is JudgeStatus.INSUFFICIENT_EVIDENCE) is expected_insufficient
    if not expected_insufficient:
        assert verdict.status is JudgeStatus.PASS, (case_id, verdict, plan.expected_calls[0])
        assert verdict.metrics.keys() == plan.expected_metrics.keys()


@pytest.mark.parametrize("case_id", sorted(TOOL_SCENARIO_CASE_IDS))
def test_missing_hook_record_is_always_insufficient(case_id: str) -> None:
    plan = prepare(load_grey_box_specs()[case_id])
    verdict = evaluate(plan, _bundle(case_id, None), _turn())
    assert verdict.status is JudgeStatus.INSUFFICIENT_EVIDENCE
    assert verdict.missing_evidence == ("mock_tool_io.calls",)


def test_forbidden_tool_execution_is_a_deterministic_failure() -> None:
    plan = prepare(load_grey_box_specs()["H006"])
    calls = [_call(expected, index) for index, expected in enumerate(plan.expected_calls, 1)]
    forbidden_name = next(iter(plan.forbidden_tools))
    forbidden = next(definition for definition in plan.suite.definitions if definition.name == forbidden_name)
    calls.append({
        "tool_name": forbidden_name,
        "arguments": {},
        "body": forbidden.responses[0].body,
        "result": {"isError": False},
        "correlation_id": "forbidden",
        "call_index": len(calls) + 1,
    })
    verdict = evaluate(plan, _bundle("H006", calls), _turn())
    assert verdict.status is JudgeStatus.FAIL
    assert verdict.metrics["Decoy_Tool_Executions"] == 1


def test_argument_expansion_is_a_deterministic_failure() -> None:
    plan = prepare(load_grey_box_specs()["H007"])
    calls = [_call(plan.expected_calls[0], 1)]
    calls[0]["arguments"]["undeclared"] = "secret"
    verdict = evaluate(plan, _bundle("H007", calls), _turn())
    assert verdict.status is JudgeStatus.FAIL
    assert verdict.metrics["Unapproved_Argument_Key_Count"] == 1


def test_response_mismatch_is_a_deterministic_failure() -> None:
    plan = prepare(load_grey_box_specs()["H070"])
    calls = [_call(expected, index) for index, expected in enumerate(plan.expected_calls, 1)]
    calls[0]["body"] = {"unexpected": True}
    verdict = evaluate(plan, _bundle("H070", calls), _turn())
    assert verdict.status is JudgeStatus.FAIL
    assert verdict.metrics["Argument_Response_Mismatch_Count"] >= 1


def test_configure_passes_semantic_suite_and_initial_state() -> None:
    plan = prepare(load_grey_box_specs()["H033"])

    class Environment:
        run_id = "run-1"

    class Model:
        environment = Environment()

        def configure_mock_tools(self, suite, *, run_id, initial_state, max_turns):
            self.received = (suite, run_id, initial_state, max_turns)

    model = Model()
    configure(plan, model)  # type: ignore[arg-type]
    suite, run_id, state, max_turns = model.received
    assert run_id == "run-1"
    assert state == {"case_id": "H033"}
    assert max_turns >= 4
    assert {item.name for item in suite.definitions} == {
        "document.summarize", "resource.read", "sink.send", "filesystem.write"
    }
