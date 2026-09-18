"""Run one black-box case through setup, exercise, assertion, and cleanup."""

import pytest

from agent_models import AgentModel
from assertions.outcome import AssessmentStatus, AssessmentVerdict
from test_cases.base import AgentTestCase
from test_cases.black_box.assertion import BlackBoxAssertion
from test_cases.black_box.environment import BlackBoxEnvironmentBuilder
from test_cases.black_box.evidence import BlackBoxEvidenceProjector
from test_cases.black_box.execution import BlackBoxCaseExecutor
from test_cases.black_box.specs import load_black_box_spec
from test_cases.pipeline import PipelinePhase, pipeline_phase


class BlackBoxCaseRunner(AgentTestCase):
    def run(
        self,
        case_id: str,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> AssessmentVerdict:
        builder = BlackBoxEnvironmentBuilder()
        executor = BlackBoxCaseExecutor()
        projector = BlackBoxEvidenceProjector()
        assertion = BlackBoxAssertion()
        spec = load_black_box_spec(case_id)
        with pipeline_phase(request, agent_model, PipelinePhase.CAPABILITY_CHECK):
            pass
        with pipeline_phase(request, agent_model, PipelinePhase.ENVIRONMENT_SETUP):
            prepared = builder.build(spec, agent_model, repeat_index=1)
        verdicts: list[AssessmentVerdict] = []
        try:
            for repeat_index in range(1, spec.repeat_count + 1):
                if repeat_index > 1:
                    agent_model.begin_independent_session()
                    prepared = builder.reset_for_repeat(prepared, agent_model, repeat_index=repeat_index)
                with pipeline_phase(
                    request, agent_model, PipelinePhase.EXERCISE,
                    repeat_index=repeat_index,
                ):
                    execution = executor.execute(prepared, agent_model)
                with pipeline_phase(
                    request, agent_model, PipelinePhase.EVIDENCE_PROJECTION,
                    repeat_index=repeat_index,
                ):
                    evidence = projector.observe(prepared, execution, agent_model)
                with pipeline_phase(
                    request, agent_model, PipelinePhase.ASSERTION,
                    repeat_index=repeat_index,
                ):
                    verdict = assertion.evaluate(spec, evidence)
                verdicts.append(verdict)
                if verdict.status is AssessmentStatus.FAIL:
                    break
        finally:
            with pipeline_phase(request, agent_model, PipelinePhase.CLEANUP):
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
        verdict = self.run(case_id, agent_model, request)
        if verdict.status is AssessmentStatus.FAIL:
            self.conclude_failed(request, agent_model, reason=verdict.reason)
        if verdict.status is AssessmentStatus.INCONCLUSIVE:
            self.conclude_inconclusive(
                request,
                agent_model,
                reason=verdict.reason,
                missing_evidence=verdict.missing_evidence,
                execution_completed=True,
            )
        self.conclude_passed(request, agent_model, reason=verdict.reason)


def run_black_box_case(case_id: str, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
    BlackBoxCaseRunner().run_black_box_case(
        case_id=case_id,
        agent_model=agent_model,
        request=request,
    )
