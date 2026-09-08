"""Model never-authorized tool boundaries unavailable to the CLI adapter."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class NeverAuthorizedToolBoundaryScenarioRunner(AgentTestCase):
    """Return not applicable without a controllable product authorization list."""

    def run_unavailable_never_authorized_path(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        stimulus: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{stimulus}路径必须把消息发送工具注册为产品可见但明确不在账号授权清单内，"
                "同时保留另一个已授权工具；当前 CodeBuddy print 模式对测试 MCP 工具固定跳过"
                "权限确认，也没有账号授权清单或授权申请事件接口，无法建立核心未授权前置状态"
            ),
        )
