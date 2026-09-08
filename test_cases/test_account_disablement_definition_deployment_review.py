"""Verify the deployed definition and availability of account disablement."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-7.2b-D1-01-S01-01"
TEST_SAMPLE_ID = "ATS-7.2b-D1-01-S01"
TEST_PROMPT_ID = "01"


class TestATS72BD101S0101AccountDisablementDefinitionDeployment(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D1-01-S01-01

    测试用例名称：停用定义与默认部署

    测试目标：
        验证账号停用入口已部署、受控、默认可用且语义是拒绝账号访问。

    前置条件：
        1. 取得当前部署材料、操作手册和服务商安全管理员权限。

    测试步骤：
        1. 核对停用入口、后端动作、开关权限及默认部署状态。

    预期结果：
        1. 停用入口已部署、受控、默认可用，并拒绝账号访问。
    """

    def test_account_disablement_definition_deployment(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架无法取得服务商部署材料、管理入口或书面确认，不能执行账号停用定义与默认部署核查",
        )
