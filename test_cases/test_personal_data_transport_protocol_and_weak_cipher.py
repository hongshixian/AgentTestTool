"""Verify personal-data transport avoids obsolete protocols and weak cipher suites."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.3a-D3-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.3a-D3-02-S01"
TEST_PROMPT_ID = "02"


class TestATS53AD302S0102PersonalDataTransportProtocolWeakCipher(AgentTestCase):
    """测试用例 ID：ATS-5.3a-D3-02-S01-02

    测试用例名称：协议版本与弱套件

    测试目标：
        验证实际承载个人信息的连接未协商失效协议或弱套件。

    前置条件：
        1. 原始旁路握手抓包和数据路径关联能力可用。
        2. 测试使用虚构姓名和电话。

    测试步骤：
        1. 现场提交虚构个人资料并抓取握手。
        2. 将协商结果关联到实际个人信息传输路径。

    预期结果：
        1. 实际连接未协商 SSLv3、TLS 1.0、NULL 或导出级套件。
        2. 协商配置和明文恢复结论分别记录。
    """

    def test_personal_data_transport_protocol_and_weak_cipher(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 STDIO 适配不采集 Agent 全部网络握手，不能把协议协商结果与实际个人信息数据路径关联，也没有产品个人资料写入接口。")
