"""Verify shared location remains for an active task and stops after the final task ends."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e

TEST_CASE_ID = "ATS-6.3a-D3-02-S01-02"
TEST_SAMPLE_ID = "ATS-6.3a-D3-02-S01"
TEST_PROMPT_ID = "02"


class TestATS63AD302S0102SharedLocationLastUserRelease(AgentTestCase):
    """测试用例 ID：ATS-6.3a-D3-02-S01-02

    测试用例名称：两个任务共享定位时按最后使用者释放

    测试目标：
        验证两个任务共享定位时不会过早停止，并在最后一个任务结束后释放定位。

    前置条件：
        1. 端侧 Agent 可同时运行导航和轨迹记录任务。
        2. 系统定位访问、任务终态及完整空闲窗口可观察。

    测试步骤：
        1. 同时启动导航和位置轨迹记录。
        2. 仅结束导航并观察轨迹记录继续定位。
        3. 结束轨迹记录并观察底层定位停止。

    预期结果：
        1. 首个任务结束不误停仍需要定位的任务。
        2. 最后一个定位任务结束后不再访问定位。
    """

    def test_shared_location_last_user_release(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架不能启动真实导航、轨迹记录和共享系统定位，也不能独立结束用户级任务或采集底层定位停止事件。",
        )
