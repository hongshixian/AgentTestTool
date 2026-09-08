"""Base class for shared Agent CLI test cases."""

import os

import pytest

from agent_models import AgentModel, EvidenceBundle, TurnResult
from assertions import (
    ASSESSMENT_MISSING_EVIDENCE_PROPERTY,
    ASSESSMENT_REASON_PROPERTY,
    ASSESSMENT_STATUS_PROPERTY,
    AssessmentOutcomeSignal,
    AssessmentStatus,
    AssessmentVerdict,
    assessment_verdict,
    mock_inconclusive_assertion,
)
from assertions.logical import (
    assert_agent_authenticated as check_agent_authenticated,
    assert_authoritative_identity_unchanged as check_authoritative_identity_unchanged,
    assert_destroyed_instance_remains_destroyed as check_destroyed_instance_remains_destroyed,
    assert_instance_inventory_unchanged as check_instance_inventory_unchanged,
    assert_local_state_tamper_detected_and_restored as check_local_state_restored,
    assert_mock_tool_called_with_configured_result as check_mock_tool_called,
    assert_protected_resources_not_accessed as check_protected_resources_not_accessed,
    assert_required_evidence as check_required_evidence,
    assert_sensitive_value_not_returned as check_sensitive_value_not_returned,
    assert_turn_completed as check_turn_completed,
)
from assertions.judge import JudgeStatus, JudgeVerdict, OpenAICompatibleJudge
from test_cases.security import SecurityIdentitySettings, SecurityTargetSettings


class AgentTestCase:
    """Common test helpers will be added here as the test suite grows."""

    def assert_agent_authenticated(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        try:
            check_agent_authenticated(agent_model)
        except AssertionError as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"被测 Agent CLI 不可用或认证失败：{error}",
            )

    def require_security_boundary_observation(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        if not agent_model.capabilities.security_boundary_observation:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason=(
                    "当前 Agent 不具备本脚本必需的完整安全边界观察能力，"
                    "无法执行该安全边界路径"
                ),
            )
        if not agent_model.capabilities.external_observation:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason="当前 Agent 缺少本脚本必需的公开黑盒观察 Provider，无法执行该安全边界路径",
            )

    def require_security_identities(
        self,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
    ) -> SecurityIdentitySettings:
        try:
            return SecurityIdentitySettings.from_environment()
        except ValueError as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"测试前置账号配置失败：{error}",
            )
            raise AssertionError("unreachable")

    def require_security_target(
        self,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
    ) -> SecurityTargetSettings:
        try:
            return SecurityTargetSettings.from_environment()
        except ValueError as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"测试前置目标配置失败：{error}",
            )
            raise AssertionError("unreachable")

    def require_environment_setting(
        self,
        name: str,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
    ) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"测试前置环境配置缺失：{name}",
            )
        return value

    def require_judge_model(
        self,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
    ) -> OpenAICompatibleJudge:
        if judge_model is None:
            self.conclude_failed(
                request,
                agent_model,
                reason="测试前置配置失败：Judge API 未配置或配置无效",
            )
        return judge_model

    def conclude_judge_verdict(
        self,
        verdict: JudgeVerdict,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
    ) -> None:
        if verdict.status is JudgeStatus.PASS:
            self.conclude_passed(request, agent_model, reason=verdict.reason)
        if verdict.status is JudgeStatus.FAIL:
            self.conclude_failed(request, agent_model, reason=verdict.reason)
        self.conclude_inconclusive(
            request,
            agent_model,
            reason=verdict.reason,
            missing_evidence=("Judge 判定所需的完整证据",),
            execution_completed=True,
        )

    def _conclude(
        self,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
        verdict: AssessmentVerdict,
    ) -> None:
        properties = (
            (ASSESSMENT_STATUS_PROPERTY, verdict.status.value),
            (ASSESSMENT_REASON_PROPERTY, verdict.reason),
            (
                ASSESSMENT_MISSING_EVIDENCE_PROPERTY,
                "；".join(verdict.missing_evidence),
            ),
        )
        request.node.user_properties.extend(properties)
        agent_model.environment.ledger.record(
            "assertion",
            "assessment_concluded",
            {
                "status": verdict.status.value,
                "reason": verdict.reason,
                "missing_evidence": list(verdict.missing_evidence),
            },
        )
        raise AssessmentOutcomeSignal(verdict)

    def conclude_passed(
        self,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
        *,
        reason: str,
    ) -> None:
        self._conclude(
            request,
            agent_model,
            assessment_verdict(AssessmentStatus.PASS, reason=reason),
        )

    def conclude_failed(
        self,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
        *,
        reason: str,
    ) -> None:
        self._conclude(
            request,
            agent_model,
            assessment_verdict(AssessmentStatus.FAIL, reason=reason),
        )

    def conclude_not_applicable(
        self,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
        *,
        reason: str,
    ) -> None:
        self._conclude(
            request,
            agent_model,
            assessment_verdict(AssessmentStatus.NOT_APPLICABLE, reason=reason),
        )

    def conclude_inconclusive(
        self,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
        *,
        reason: str,
        missing_evidence: tuple[str, ...],
        execution_completed: bool,
    ) -> None:
        """Record evidence insufficiency after all required functional steps completed."""
        verdict = mock_inconclusive_assertion(
            reason=reason,
            missing_evidence=missing_evidence,
            execution_completed=execution_completed,
        )
        self._conclude(request, agent_model, verdict)

    def assert_turn_completed(
        self,
        turn: TurnResult,
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
    ) -> None:
        try:
            check_turn_completed(turn)
        except AssertionError as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"测试刺激未完成：{error}",
            )

    def assert_sensitive_value_not_returned(
        self,
        evidence: EvidenceBundle,
        *,
        sensitive_value: str,
    ) -> None:
        check_sensitive_value_not_returned(
            evidence,
            sensitive_value=sensitive_value,
        )

    def assert_required_evidence(
        self,
        evidence: EvidenceBundle,
        required_evidence_ids: set[str],
        expected_external_types: dict[str, str] | None = None,
    ) -> None:
        check_required_evidence(
            evidence,
            required_evidence_ids,
            expected_external_types,
        )

    def require_evidence_or_conclude_inconclusive(
        self,
        evidence: EvidenceBundle,
        required_evidence_ids: set[str],
        request: pytest.FixtureRequest,
        agent_model: AgentModel,
        expected_external_types: dict[str, str] | None = None,
    ) -> None:
        """Require assessment evidence or explicitly return unable to determine."""
        try:
            self.assert_required_evidence(
                evidence,
                required_evidence_ids,
                expected_external_types,
            )
        except AssertionError as error:
            self.conclude_inconclusive(
                request,
                agent_model,
                reason=str(error),
                missing_evidence=tuple(
                    sorted(evidence.missing_evidence(required_evidence_ids))
                )
                or ("符合类型要求的完整外部证据",),
                execution_completed=True,
            )

    def assert_authoritative_identity_unchanged(
        self,
        evidence: EvidenceBundle,
        *,
        expected_user_id: str,
        expected_instance_id: str,
    ) -> None:
        check_authoritative_identity_unchanged(
            evidence,
            expected_user_id=expected_user_id,
            expected_instance_id=expected_instance_id,
        )

    def assert_protected_resources_not_accessed(
        self,
        evidence: EvidenceBundle,
        *,
        private_marker: str,
        authorization_marker: str,
    ) -> None:
        check_protected_resources_not_accessed(
            evidence,
            private_marker=private_marker,
            authorization_marker=authorization_marker,
        )

    def assert_mock_tool_called_with_configured_result(
        self,
        evidence: EvidenceBundle,
        *,
        expected_tool_name: str,
        expected_content_type: str,
        expected_body: object,
    ) -> None:
        check_mock_tool_called(
            evidence,
            expected_tool_name=expected_tool_name,
            expected_content_type=expected_content_type,
            expected_body=expected_body,
        )

    def assert_instance_inventory_unchanged(self, evidence: EvidenceBundle) -> None:
        check_instance_inventory_unchanged(evidence)

    def assert_destroyed_instance_remains_destroyed(
        self,
        evidence: EvidenceBundle,
        *,
        destroyed_instance_id: str,
    ) -> None:
        check_destroyed_instance_remains_destroyed(
            evidence,
            destroyed_instance_id=destroyed_instance_id,
        )

    def assert_local_state_tamper_detected_and_restored(
        self,
        evidence: EvidenceBundle,
        *,
        target_instance_id: str,
    ) -> None:
        check_local_state_restored(
            evidence,
            target_instance_id=target_instance_id,
        )
