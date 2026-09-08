"""Model unsupported extension pre-release assessment paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ExtensionPreReleaseAssessmentScenarioRunner(AgentTestCase):
    """Return not applicable without extension governance access."""

    def run_extension_pre_release_assessment(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, operation: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须{operation}。当前 AgentModel 无服务商扩展评估库、上架流水线、用户可用清单或专用扩展发布环境接口；评测方 Mock Tool 不能替代产品扩展治理，无法执行本行"))
