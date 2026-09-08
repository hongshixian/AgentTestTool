"""Model native risk-notice decision paths unavailable to print-mode CLI tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class RiskNoticeInformationScenarioRunner(AgentTestCase):
    """Return not applicable without a controllable product authorization UI."""

    def run_unavailable_risk_notice_path(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        operation: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{operation}告知核查必须停在产品首次可点击授权或接管界面，读取首屏"
                "最终渲染文案和可访问性树，并实际选择拒绝；当前 CodeBuddy print 模式"
                "固定跳过工具权限确认，不提供图形决策界面、点击或授权事件接口，无法执行"
            ),
        )
