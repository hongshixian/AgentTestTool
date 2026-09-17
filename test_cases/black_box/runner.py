"""Run one black-box case through setup, exercise, assertion, and cleanup."""

import pytest

from agent_models import AgentModel
from assertions.outcome import AssessmentOutcomeSignal, AssessmentStatus, AssessmentVerdict
from test_cases.black_box.assertion import BlackBoxAssertion
from test_cases.black_box.environment import BlackBoxEnvironmentBuilder
from test_cases.black_box.evidence import BlackBoxEvidenceProjector
from test_cases.black_box.execution import BlackBoxCaseExecutor
from test_cases.black_box.specs import load_black_box_spec


class BlackBoxCaseRunner:
    def run(self, case_id: str, agent_model: AgentModel) -> AssessmentVerdict:
        builder = BlackBoxEnvironmentBuilder()
        executor = BlackBoxCaseExecutor()
        projector = BlackBoxEvidenceProjector()
        assertion = BlackBoxAssertion()
        spec = load_black_box_spec(case_id)
        prepared = builder.build(spec, agent_model, repeat_index=1)
        verdicts: list[AssessmentVerdict] = []
        try:
            for repeat_index in range(1, spec.repeat_count + 1):
                if repeat_index > 1:
                    agent_model.begin_independent_session()
                    prepared = builder.reset_for_repeat(prepared, agent_model, repeat_index=repeat_index)
                ledger = agent_model.environment.ledger
                ledger.record("black_box", "phase_started",
                              {"case_id": case_id, "repeat_index": repeat_index, "phase": "exercise"})
                execution = executor.execute(prepared, agent_model)
                ledger.record("black_box", "phase_completed",
                              {"case_id": case_id, "repeat_index": repeat_index, "phase": "exercise"})
                evidence = projector.observe(prepared, execution, agent_model)
                ledger.record("black_box", "phase_started",
                              {"case_id": case_id, "repeat_index": repeat_index, "phase": "assertion"})
                verdict = assertion.evaluate(spec, evidence)
                verdicts.append(verdict)
                ledger.record("black_box", "phase_completed",
                              {"case_id": case_id, "repeat_index": repeat_index, "phase": "assertion",
                               "status": verdict.status.value})
                if verdict.status is AssessmentStatus.FAIL:
                    break
        finally:
            builder.cleanup(prepared, agent_model)
        failed = next((item for item in verdicts if item.status is AssessmentStatus.FAIL), None)
        inconclusive = next((item for item in verdicts if item.status is AssessmentStatus.INCONCLUSIVE), None)
        return failed or inconclusive or AssessmentVerdict(
            AssessmentStatus.PASS, f"{case_id} 的 {len(verdicts)} 个独立重复组均通过")

    def run_black_box_case(
        self,
        *,
        case_id: str,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        _conclude(self.run(case_id, agent_model), agent_model, request)


def run_black_box_case(case_id: str, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
    _conclude(BlackBoxCaseRunner().run(case_id, agent_model), agent_model, request)


def _conclude(
    verdict: AssessmentVerdict,
    agent_model: AgentModel,
    request: pytest.FixtureRequest,
) -> None:
    request.node.user_properties.extend((("assessment_status", verdict.status.value),
                                         ("assessment_reason", verdict.reason),
                                         ("assessment_missing_evidence", "；".join(verdict.missing_evidence))))
    agent_model.environment.ledger.record("assertion", "assessment_concluded",
                                          {"status": verdict.status.value, "reason": verdict.reason,
                                           "missing_evidence": list(verdict.missing_evidence)})
    raise AssessmentOutcomeSignal(verdict)
