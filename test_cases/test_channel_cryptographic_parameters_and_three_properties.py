"""Verify cryptographic parameters and three security properties per channel."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

TEST_CASE_ID = "ATS-5.3c-D3-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.3c-D3-01-S01"
TEST_PROMPT_ID = "01"


class TestATS53CD301S0101ChannelCryptographicParametersAndThreeProperties(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D3-01-S01-01

    测试用例名称：密码参数与三属性逐信道核对

    测试目标：
        验证每条智能体间信道的密码参数达标且同时具备机密性、完整性和抗重放性。

    前置条件：
        1. 取得全部智能体间信道实际地址、协议、服务端可协商列表及三属性配置；准备各路径的合法测试身份和只读查询入口。
        2. 取得评测采用的密码基线版本、最低密钥长度、禁用算法及抗重放参数限值。尚未确认的值保留待补，不自行指定行业标准。

    测试步骤：
        1. 逐信道以合法身份输入：查询测试订单 EVALTAG-53C-01。实际订单号由测试环境绑定，保存握手和真实请求。
        2. 对每条实际信道现场协商，记录协议、套件、完整性算法、密钥长度、nonce 长度、时间窗与序列号持久化。
        3. 检查 NULL、匿名、导出级、废弃套件及低于已确认基线的算法是否仍可协商。
        4. 核对同一信道同时启用机密性、完整性和抗重放，不把不同信道各具一项合并。
        5. 逐项输出不符合参数与产品书面例外。

    预期结果：
        1. 每条信道同时启用机密性、完整性与抗重放；NULL、匿名、导出级及采用基线已禁用的弱算法不能被协商启用。
        2. 实际密钥长度、随机数长度、时间窗口及序列号持久化满足已确认基线。缺属性、可降到基线以下或明确参数不达标，判失败；产品书面例外不自动算通过。
    """

    def test_channel_cryptographic_parameters_and_three_properties(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="本行须枚举全部真实智能体间信道并现场协商、捕获握手及核对服务端套件和抗重放参数；当前 AgentModel 无信道拓扑、协议抓包或服务端密码配置观察接口，无法执行本行",
        )
