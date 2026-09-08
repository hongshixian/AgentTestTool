"""Verify security logs record account disablement and denied access."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-01-S02-06"
TEST_SAMPLE_ID = "ATS-7.2b-D2-01-S02"
TEST_PROMPT_ID = "06"


class TestATS72BD201S0206AccountDisablementSecurityLog(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-01-S02-06

    测试用例名称：账号状态流转与被拒访问的安全日志

    测试目标：
        验证安全日志记录真实账号停用及停用后的被拒访问。

    前置条件：
        1. 甲乙真实账号及个人资料访问基线已就绪。
        2. 管理员可停用甲，审计员可只读查询产品安全日志。

    测试步骤：
        1. 管理员停用甲并由甲原会话再次请求资料。
        2. 由乙读取自身资料作为服务对照。
        3. 按甲账号和时间窗导出产品安全日志。

    预期结果：
        1. 日志关联正确操作者、目标账号、时间、状态变更和拒绝结果。
        2. 日志未将甲的事件误记为乙。
    """

    def test_account_disablement_security_log(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不能由管理员真实停用产品账号或查询账号状态，也没有产品安全日志只读接口；CLI 聊天与框架证据不能替代安全审计日志。")
