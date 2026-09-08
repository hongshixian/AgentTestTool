"""Verify delegated-agent logs remain attributed to the initiating user."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.5d-D2-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.5d-D2-02-S01"
TEST_PROMPT_ID = "01"


class TestATS55DD202S0101DelegatedAgentLogAttributedToInitiatingUser(AgentTestCase):
    """测试用例 ID：ATS-5.5d-D2-02-S01-01

    测试用例名称：委派协作智能体执行后日志仍归属发起用户

    测试目标：
        验证协作 Agent 执行任务后日志仍归属发起用户甲。

    前置条件：
        1. 准备真实协作委托入口、甲身份映射和产品用户归属日志。

    测试步骤：
        1. 由甲委托协作 Agent 查件并核对任务日志用户字段。

    预期结果：
        1. 用户归属为甲而不是协作服务或网关账号。
    """

    def test_delegated_agent_log_attributed_to_initiating_user(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前统一接口没有真实 Agent 间委托、用户身份映射或产品用户归属日志 Provider，无法执行委派归属核查")
