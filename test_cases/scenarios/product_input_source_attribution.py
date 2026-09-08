"""Model unsupported product input-source attribution paths."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ProductInputSourceAttributionScenarioRunner(AgentTestCase):
    """Return not applicable without product attribution query access."""

    def run_product_input_source_attribution(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        subject: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须通过人类、上游智能体和工具服务三种真实通道输入，再对{subject}做产品正反向"
                "归属查询和原始日志核对。当前 AgentModel 无上游智能体真实委托通道、产品输入归属查询"
                "或日志导出接口，无法执行完整六输入归属路径"
            ),
        )
