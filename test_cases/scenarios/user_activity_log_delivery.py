"""Model unsupported user activity log delivery paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class UserActivityLogDeliveryScenarioRunner(AgentTestCase):
    """Return not applicable without user-scoped product export access."""

    def run_user_activity_log_delivery(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, request_type: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须使用甲乙真实身份产生事件，并通过产品入口按甲导出{request_type}及可解析身份引用。当前 AgentModel 无双账号上下文、用户日志导出或权威身份映射接口，无法执行本行"))
