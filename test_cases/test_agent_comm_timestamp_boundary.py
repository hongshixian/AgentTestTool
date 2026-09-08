"""Verify timestamp replay protection at the declared acceptance boundaries."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D4-01-S01-06"
TEST_SAMPLE_ID = "ATS-5.3c-D4-01-S01"
TEST_PROMPT_ID = "06"


class TestATS53CD401S0106AgentCommTimestampBoundary(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D4-01-S01-06

    测试用例名称：时间戳在接受窗口内外时按声明边界处理

    测试目标：
        验证时间戳抗重放机制按声明的接受窗口处理边界消息。

    前置条件：
        1. 产品使用时间戳机制保护智能体间通信。
        2. 已取得过去和未来允许偏差及边界包含规则。
        3. 可控制已认证消息的时间戳并为每条消息使用新标识。
        4. 可取得接收端可信时间、校验结论和业务处理记录。

    测试步骤：
        1. 使用当前可信时间发送新鲜查询。
        2. 分别在每个时间边界的内侧和外侧发送新鲜查询。
        3. 核对每条消息的实际时间偏差和处理结果。

    预期结果：
        1. 正常消息和接受范围内的有效消息可正常处理。
        2. 接受范围外的消息被时间戳检查拒绝。
        3. 实际接受范围与产品声明一致。
    """

    def test_agent_comm_timestamp_boundary(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 未暴露真实智能体通信的时间戳字段、声明窗口或边界包含规则，"
                "也不能取得接收端可信时间和业务处理记录，无法执行时间窗边界试验"
            ),
        )
