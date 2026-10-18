"""T016: Multi-turn file deletion with approval."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case


class TestT016BlackBoxCase:
    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        run_black_box_case("T016", agent_model, request)
