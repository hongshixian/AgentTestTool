"""Base class for shared Agent CLI test cases."""

from agent_models import AgentModel, EvidenceBundle, TurnResult
from assertions.logical import (
    assert_agent_authenticated as check_agent_authenticated,
    assert_authoritative_identity_unchanged as check_authoritative_identity_unchanged,
    assert_protected_resources_not_accessed as check_protected_resources_not_accessed,
    assert_required_evidence as check_required_evidence,
    assert_turn_completed as check_turn_completed,
)


class AgentTestCase:
    """Common test helpers will be added here as the test suite grows."""

    def assert_agent_authenticated(self, agent_model: AgentModel) -> None:
        check_agent_authenticated(agent_model)

    def assert_turn_completed(self, turn: TurnResult) -> None:
        check_turn_completed(turn)

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
        forbidden_user_id: str,
        forbidden_instance_id: str,
        private_marker: str,
        authorization_marker: str,
    ) -> None:
        check_protected_resources_not_accessed(
            evidence,
            forbidden_user_id=forbidden_user_id,
            forbidden_instance_id=forbidden_instance_id,
            private_marker=private_marker,
            authorization_marker=authorization_marker,
        )
