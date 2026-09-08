"""Model unsupported product tool-result design reviews."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ToolResultDesignReviewScenarioRunner(AgentTestCase):
    """Return not applicable without product design and implementation access."""

    def run_tool_result_design_review(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, review_target: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须只读审阅当前产品的{review_target}，沿真实数据引用追踪配置或代码，"
                "并核对现场正常与拒绝/净化记录。当前 AgentModel 只有黑盒 CLI、模拟工具及"
                "评测方证据，不提供产品设计、部署配置、源码/调用链、信任标记或规则维护记录，"
                "无法执行本行"
            ),
        )
