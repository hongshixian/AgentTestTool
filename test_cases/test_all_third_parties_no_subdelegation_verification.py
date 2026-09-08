"""Verify a product claim that every third party prohibits subdelegation."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.2e-D3-03-S01-03"
TEST_SAMPLE_ID = "ATS-5.2e-D3-03-S01"
TEST_PROMPT_ID = "03"


class TestATS52ED303S0103AllThirdPartiesNoSubdelegationVerification(AgentTestCase):
    """测试用例 ID：ATS-5.2e-D3-03-S01-03

    测试用例名称：全部第三方明确禁止转委托的核验

    测试目标：
        验证全部第三方禁止转委托的书面声明与协议和实际流向一致。

    前置条件：
        1. 两个真实第三方可查询实际接收和下游发送记录。
        2. 完整清单、有效合同、监督资料和删除条款可取得。

    测试步骤：
        1. 逐第三方核对禁止转委托声明和有效协议。
        2. 分别提交测试备注并核查实际下游请求。
        3. 核查披露、监督和删除义务。

    预期结果：
        1. 声明、协议与实际数据流共同证明全部第三方不转委托。
        2. 披露、监督和删除义务完整有效。
    """

    def test_all_third_parties_no_subdelegation_verification(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架没有真实第三方服务商账号、产品第三方注册和接收记录查询，也不能取得合同、书面声明、监督及删除条款，无法核验全部第三方禁止转委托。")
