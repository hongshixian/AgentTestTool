"""Base class for shared Agent CLI test cases."""

from agent_models import AgentModel, TurnResult
from assertions.logical import (
    assert_agent_authenticated as check_agent_authenticated,
    assert_turn_completed as check_turn_completed,
)


class AgentTestCase:
    """Common test helpers will be added here as the test suite grows."""

    def assert_agent_authenticated(self, agent_model: AgentModel) -> None:
        check_agent_authenticated(agent_model)

    def assert_turn_completed(self, turn: TurnResult) -> None:
        check_turn_completed(turn)
