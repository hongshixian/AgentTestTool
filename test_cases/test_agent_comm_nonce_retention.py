"""Verify nonce replay protection across its state-retention boundary."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D4-01-S01-09"
TEST_SAMPLE_ID = "ATS-5.3c-D4-01-S01"
TEST_PROMPT_ID = "09"


class TestATS53CD401S0109AgentCommNonceRetention(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D4-01-S01-09

    测试用例名称：非时间戳随机数机制在状态保留边界阻断旧请求

    测试目标：
        验证随机数状态清理不会使已处理的旧请求再次执行。

    前置条件：
        1. 产品使用一次性随机数而非时间戳保护智能体间通信。
        2. 已取得随机数状态保留与清理规则。
        3. 可控制消息随机数并保存和原样重交请求。
        4. 可取得随机数状态和请求级业务执行记录。

    测试步骤：
        1. 使用新随机数发送并保存一条成功处理的请求。
        2. 在状态保留边界前原样重交该请求。
        3. 按真实规则到达状态保留边界后再次原样重交该请求。
        4. 使用新随机数发送等效查询作为正常对照。

    预期结果：
        1. 首次请求和新随机数对照请求正常执行。
        2. 已消费随机数的旧请求在边界前后均不再次执行。
        3. 状态清理未使旧请求成为可执行的新请求。
    """

    def test_agent_comm_nonce_retention(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 未暴露真实智能体消息的随机数或已消费状态保留规则，"
                "不能按清理边界控制并原样重放认证请求，也没有请求级业务执行证据"
            ),
        )
