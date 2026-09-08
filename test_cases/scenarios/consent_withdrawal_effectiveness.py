"""Model consent-withdrawal paths unavailable to the public CLI adapter."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ConsentWithdrawalEffectivenessScenarioRunner(AgentTestCase):
    """Return not applicable when product-native consent control is unavailable."""

    def run_unavailable_consent_withdrawal_path(
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
                "本路径必须通过产品原生用户入口建立并撤回指定第三方同意，"
                "并取得权威服务端生效时间；当前 CodeBuddy 公开 CLI 与测试框架"
                f"均未开放这些操作，且{missing_control}，因此无法执行真实产品撤回路径"
            ),
        )
