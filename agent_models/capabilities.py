"""Capabilities exposed consistently to shared test cases."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentCapabilities:
    """Execution conditions consumed by cases before explicit four-state assertions."""

    authentication: bool = True
    prompt: bool = True
    multi_turn: bool = False
    file_operations: bool = False
    dedicated_test_account: bool = False
    external_observation: bool = False
    # Requires verified public evidence of identity use, data access and auth events.
    security_boundary_observation: bool = False
    mock_tools: bool = False
    multiple_mock_tools: bool = False
    controlled_environment: bool = False
    public_identity_context: bool = False
    local_state_control: bool = False
    interactive_session: bool = False
    independent_sessions: bool = False
    streaming_events: bool = False
    runtime_control: bool = False
    permission_control: bool = False
    background_task_events: bool = False
    product_runtime_evidence: bool = False
    session_correlation_evidence: bool = False
    tool_event_evidence: bool = False
    permission_event_evidence: bool = False
    task_event_evidence: bool = False
    authoritative_identity_evidence: bool = False
    authorization_evidence: bool = False
    security_event_evidence: bool = False
    resource_state_evidence: bool = False
