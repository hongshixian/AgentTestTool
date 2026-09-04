"""Base class for shared Agent CLI test cases."""

import os

import pytest

from agent_models import AgentModel, EvidenceBundle, TurnResult
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
from test_cases.security import SecurityIdentitySettings, SecurityTargetSettings


class AgentTestCase:
    """Common test helpers will be added here as the test suite grows."""

    def assert_agent_authenticated(self, agent_model: AgentModel) -> None:
        check_agent_authenticated(agent_model)

    def require_security_identities(self) -> SecurityIdentitySettings:
        try:
            return SecurityIdentitySettings.from_environment()
        except ValueError as error:
            pytest.skip(str(error))

    def require_security_target(self) -> SecurityTargetSettings:
        try:
            return SecurityTargetSettings.from_environment()
        except ValueError as error:
            pytest.skip(str(error))

    def require_environment_setting(self, name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            pytest.skip(f"缺少真实测试环境配置：{name}")
        return value

    def assert_turn_completed(self, turn: TurnResult) -> None:
        check_turn_completed(turn)

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
