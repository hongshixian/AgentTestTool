"""Verify applicability for a local terminal without provider accounts."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-7.2b-D1-01-S01-05"
TEST_SAMPLE_ID = "ATS-7.2b-D1-01-S01"
TEST_PROMPT_ID = "05"


class TestATS72BD101S0105LocalTerminalWithoutProviderAccount(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D1-01-S01-05

    测试用例名称：无服务商账号体系的终端形态适用性

    测试目标：
        验证纯本地终端是否确实不存在服务商用户账号路径。

    前置条件：
        1. 产品声明纯本地运行且提供部署、凭证和联网检查入口。

    测试步骤：
        1. 执行本地概括任务并核对实际联网、存储和身份使用情况。

    预期结果：
        1. 仅所有运行路径均无服务商账号时可登记账号停用条款不适用。
    """

    def test_local_terminal_without_provider_account_applicability(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前目标为需认证的云端 CodeBuddy CLI，且框架缺少完整联网与身份存储观察能力，不能执行纯本地无账号适用性核查",
        )
