"""Capabilities exposed consistently to shared test cases."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentCapabilities:
    """Feature switches used to decide which shared cases apply."""

    authentication: bool = True
    prompt: bool = True
    multi_turn: bool = False
    file_operations: bool = False
    dedicated_test_account: bool = False
    external_observation: bool = False
    mock_tools: bool = False
    public_identity_context: bool = False
    local_state_control: bool = False
