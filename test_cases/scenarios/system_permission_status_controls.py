"""Model unsupported system-permission status and disable-control paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class SystemPermissionStatusControlScenarioRunner(AgentTestCase):
    """Return not applicable without terminal permission and UI controls."""

    def run_system_permission_status_control(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, permission: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须在专用终端授予并持续使用{permission}，同步观察系统级访问、解密出站、"
                "应用实时状态展示和用户操作，再通过应用内逐权限入口禁用并验证另一权限不受影响。"
                "当前 CodeBuddy CLI 适配没有终端系统权限、前台 UI、状态展示、逐权限禁用或系统"
                "访问时间线控制与观察能力，无法执行本行"
            ),
        )
