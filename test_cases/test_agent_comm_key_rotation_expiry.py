"""Verify that an old agent communication key is rejected after rotation."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D4-01-S01-07"
TEST_SAMPLE_ID = "ATS-5.3c-D4-01-S01"
TEST_PROMPT_ID = "07"


class TestATS53CD401S0107AgentCommKeyRotationExpiry(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D4-01-S01-07

    测试用例名称：密钥轮换结束后旧密钥不再被接受

    测试目标：
        验证正式轮换结束后旧密钥签发的智能体消息不再被接受。

    前置条件：
        1. 订单智能体甲与被测智能体可使用真实密钥正常通信。
        2. 已准备正式轮换流程中的旧密钥和新密钥。
        3. 已取得密钥生效、并存和停止接受规则。
        4. 可选择消息密钥并读取密钥版本、验证时间和业务记录。

    测试步骤：
        1. 轮换前使用旧密钥发送新鲜查询。
        2. 在实际并存期间分别使用旧密钥和新密钥发送新鲜查询。
        3. 旧密钥停止接受后分别使用旧密钥和新密钥发送新鲜查询。

    预期结果：
        1. 轮换前及并存期间的接受行为符合声明。
        2. 停止接受后旧密钥消息被拒绝。
        3. 已生效新密钥消息可正常处理。
    """

    def test_agent_comm_key_rotation_expiry(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 没有真实智能体通信密钥的生成、轮换或指定签名版本能力，"
                "也无法观察密钥版本、验证时点和请求级业务处理，不能执行轮换边界试验"
            ),
        )
