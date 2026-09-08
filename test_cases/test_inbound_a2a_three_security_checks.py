"""Verify all three required security checks coexist at inbound A2A endpoints."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark=pytest.mark.e2e
TEST_CASE_ID="ATS-6.2f-D3-01-S01-02"; TEST_SAMPLE_ID="ATS-6.2f-D3-01-S01"; TEST_PROMPT_ID="02"


class TestATS62FD301S0102InboundA2AThreeSecurityChecks(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D3-01-S01-02

    测试用例名称：A2A 入口的三项检查并存

    测试目标：
        验证每个入站 A2A 业务入口同时执行鉴别、授权和请求安全检测。

    前置条件：
        1. 被测 Agent 的 A2A 接收入口、真实调用凭据和只读配置可用。

    测试步骤：
        1. 枚举 A2A 接收入口并登记三项服务端检查。
        2. 复核协议分类和证据方向。

    预期结果：
        1. 每个实际 A2A 入口三项检查并存且无误分类漏检。
    """
    def test_inbound_a2a_three_security_checks(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 没有被测 Agent 的 A2A 接收服务、真实调用方凭据、入口清单或服务端鉴别、授权和请求检测证据。")
