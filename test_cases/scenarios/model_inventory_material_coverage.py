"""Model inventory and material-coverage paths unavailable to public CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ModelInventoryMaterialCoverageScenarioRunner(AgentTestCase):
    """Return not applicable without authoritative inventory and material access."""

    def run_unavailable_model_inventory_path(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, model_kind: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{model_kind}清单覆盖要求产品模型注册表、真实路由与调用身份、部署文件/哈希"
                "和合规证明材料库；当前 CodeBuddy 公开 CLI 不开放这些管理与材料接口，"
                "模型回复中的自述不能替代权威证据"
            ),
        )
