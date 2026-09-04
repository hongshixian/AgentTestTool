"""Reusable traditional assertions based on deterministic logic."""

from agent_models import AgentModel, TurnResult


def assert_agent_authenticated(agent_model: AgentModel) -> None:
    authentication = agent_model.check_authentication()
    assert authentication.authenticated, authentication.detail


def assert_turn_completed(turn: TurnResult) -> None:
    detail = turn.stderr or turn.raw_output[-1000:]
    assert turn.completed, detail

