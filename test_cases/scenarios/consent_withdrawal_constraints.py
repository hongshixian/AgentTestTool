"""Model product-native consent-withdrawal constraint paths unavailable to CLI tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ConsentWithdrawalConstraintsScenarioRunner(AgentTestCase):
    """Return not applicable when product consent interfaces cannot be operated."""

    def run_unavailable_withdrawal_constraint_path(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        missing_control: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "本路径必须操作产品原生的提供者级同意撤回入口并取得权威服务端状态；"
                f"当前 CodeBuddy 公开 CLI {missing_control}，无法执行真实产品撤回约束测试"
            ),
        )
