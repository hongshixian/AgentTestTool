"""Verify reversible encoding is not accepted as encryption for personal data."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.3a-D3-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.3a-D3-02-S01"
TEST_PROMPT_ID = "01"


class TestATS53AD302S0101ReversibleEncodingAsEncryption(AgentTestCase):
    """测试用例 ID：ATS-5.3a-D3-02-S01-01

    测试用例名称：可逆编码冒充加密

    测试目标：
        验证原始网络包中的可逆编码不能冒充个人信息加密。

    前置条件：
        1. 原始旁路抓包和独立可读流量核对通道可用。
        2. 测试使用虚构姓名和电话。

    测试步骤：
        1. 现场提交虚构个人资料并保存完整原始网络包。
        2. 对未加密网络部分尝试常见解码和解压。

    预期结果：
        1. 未授权观察者不能从未加密网络部分还原个人信息。
        2. 还原链与原始包可关联复核。
    """

    def test_reversible_encoding_as_encryption(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 STDIO 框架没有全链路原始旁路抓包、独立可读流量核对或产品个人资料写入接口，不能区分加密层内编码与网络明文并执行还原核查。")
