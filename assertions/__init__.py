"""Traditional and intelligent assertions for Agent CLI test cases."""

from assertions.logical import (
    assert_agent_authenticated,
    assert_authoritative_identity_unchanged,
    assert_destroyed_instance_remains_destroyed,
    assert_instance_inventory_unchanged,
    assert_local_state_tamper_detected_and_restored,
    assert_mock_tool_called_with_configured_result,
    assert_protected_resources_not_accessed,
    assert_required_evidence,
    assert_turn_completed,
)
from assertions.outcome import (
    ASSESSMENT_MISSING_EVIDENCE_PROPERTY,
    ASSESSMENT_REASON_PROPERTY,
    ASSESSMENT_STATUS_PROPERTY,
    AssessmentStatus,
    AssessmentVerdict,
    mock_inconclusive_assertion,
)

__all__ = [
    "ASSESSMENT_MISSING_EVIDENCE_PROPERTY",
    "ASSESSMENT_REASON_PROPERTY",
    "ASSESSMENT_STATUS_PROPERTY",
    "AssessmentStatus",
    "AssessmentVerdict",
    "assert_agent_authenticated",
    "assert_authoritative_identity_unchanged",
    "assert_destroyed_instance_remains_destroyed",
    "assert_instance_inventory_unchanged",
    "assert_local_state_tamper_detected_and_restored",
    "assert_mock_tool_called_with_configured_result",
    "assert_protected_resources_not_accessed",
    "assert_required_evidence",
    "assert_turn_completed",
    "mock_inconclusive_assertion",
]
