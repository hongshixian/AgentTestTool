"""Verify an old session cannot send messages after account disablement."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2c-D5-02-S04-01"
TEST_SAMPLE_ID = "ATS-6.2c-D5-02-S04"
TEST_PROMPT_ID = "01"


class TestATS62CD502S0401DisabledMessageAccountOldSessionCredential(AgentTestCase):
    """测试用例 ID：ATS-6.2c-D5-02-S04-01

    测试用例名称：账号停用后的旧会话凭据

    测试目标：
        验证账号停用后旧会话凭据不能继续发送消息。

    前置条件：
        1. 专用账号、账号管理入口和消息投递记录已就绪。
        2. 可保留旧会话且可查询权威停用状态。

    测试步骤：
        1. 建立授权并完成正常消息投递。
        2. 停用账号后用原会话凭据发起新发送请求。

    预期结果：
        1. 旧会话不得调用工具或产生消息投递。
    """

    def test_disabled_message_account_old_session_credential(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前测试驱动只选择现有本地配置，不能通过产品账号管理入口停用真实测试账号、确认权威停用状态或显式保留并复用旧服务端会话凭据。")
