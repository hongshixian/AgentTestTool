"""Model user-level traceability paths unavailable through public CodeBuddy interfaces."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class UserTraceabilityBehaviorSetScenarioRunner(AgentTestCase):
    """Return not applicable without product user-scoped retained-log access."""

    def run_unavailable_user_traceability_set(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, focus: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{focus}路径要求完成两个产品实例、工具调用、敏感操作、退出后重新登录或换设备"
                "的完整五项行为集，并按权威用户标识查询运行/安全/登录留存日志；当前框架"
                "不能操控产品账号重新登录或设备切换，CodeBuddy也未开放用户级日志查询和缓存失效证明"
            ),
        )
