"""Base class for shared Agent CLI test cases."""

from agent_models import AgentModel, TurnResult


class AgentTestCase:
    """Common test helpers will be added here as the test suite grows."""

    def assert_agent_authenticated(self, agent_model: AgentModel) -> None:
        authentication = agent_model.check_authentication()
        assert authentication.authenticated, authentication.detail

    def assert_turn_completed(self, turn: TurnResult) -> None:
        detail = turn.stderr or turn.raw_output[-1000:]
        assert turn.completed, detail

