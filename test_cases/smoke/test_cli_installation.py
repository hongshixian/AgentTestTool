"""Verify that the target Agent CLI executable is installed."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]
TEST_CASE_ID = "ATS-0.0x-D0-00-S01"


class TestATS00XD000S01CLIInstallation(AgentTestCase):
    """测试用例 ID：ATS-0.0x-D0-00-S01（本条用例是示例用例）

    测试用例名称：Agent CLI 安装状态检查（冒烟示例）

    测试目标：
        验证目标 Agent CLI 命令已安装且可由测试驱动解析。

    前置条件：
        1. 已按照目标产品要求配置 CLI 命令名称。

    测试步骤：
        1. 初始化 Agent Model。
        2. 通过统一测试驱动检查 CLI 命令安装状态。

    预期结果：
        1. 测试驱动能够解析目标 Agent CLI 可执行文件。
    """

    def test_agent_cli_is_installed(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.assert_agent_installed(agent_model, request)
        self.conclude_passed(
            request,
            agent_model,
            reason="测试驱动已解析到目标 Agent CLI 可执行文件",
        )
