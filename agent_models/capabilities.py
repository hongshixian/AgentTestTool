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
