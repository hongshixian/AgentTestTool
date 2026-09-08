"""Model cloud-consent traceability paths unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class CloudConsentTraceabilityScenarioRunner(AgentTestCase):
    """Return not applicable without terminal consent and cloud log access."""

    def run_unavailable_cloud_consent(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, choice: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(f"{choice}上云路径要求终端图片提交、产品告知选择界面及告知/传输/云处理日志查询；当前CodeBuddy CLI适配器没有终端同意状态控制、图片上云链路或产品服务端日志接口，无法完成核心操作"),
        )
