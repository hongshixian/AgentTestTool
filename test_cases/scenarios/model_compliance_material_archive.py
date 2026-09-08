"""Model unsupported model-compliance material archive paths."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ModelComplianceMaterialArchiveScenarioRunner(AgentTestCase):
    """Return not applicable without product compliance material access."""

    def run_model_compliance_material_archive(
        self, agent_model: AgentModel, request: pytest.FixtureRequest, *, operation: str
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须{operation}。当前 AgentModel 不提供服务商模型注册表、真实路由元数据、合规"
                "材料库、上线核验流程或配置审计入口；CLI 自述不能替代实际模型和材料证据，无法执行本行"
            ),
        )
