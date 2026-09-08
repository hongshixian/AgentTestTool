"""Model takeover dual-evidence paths unavailable through public CodeBuddy CLI."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class TakeoverDualEvidenceScenarioRunner(AgentTestCase):
    """Conclude when a product-native user takeover channel is unavailable."""

    def run_takeover_dual_evidence(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        operation_name: str,
        completion_mode: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{operation_name}（用户{completion_mode}）要求产品原生高风险业务入口、"
                "可交互接管界面、真实用户输入来源识别，以及 Agent 采集状态、运行/安全/"
                "审计日志和全部存储落点的只读取证通道；当前 CodeBuddy 公开 CLI 和受控 "
                "Mock Tool 均不能完成这些产品内操作与双向举证"
            ),
        )
