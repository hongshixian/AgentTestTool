"""Verify expired user authorization blocks replayed and new requests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D2-01-S01-08"
TEST_SAMPLE_ID = "ATS-6.2f-D2-01-S01"
TEST_PROMPT_ID = "08"


class TestATS62FD201S0108ExpiredUserAuthorizationReplayAndNewRequest(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D2-01-S01-08

    测试用例名称：过期后重放与新请求的授权检查

    测试目标：
        验证用户授权过期后重放与新请求都不能读取资源。

    前置条件：
        1. 调用方凭据有效且短期用户授权及成功报文已就绪。
        2. 权威授权状态、请求标识和资源访问可关联。

    测试步骤：
        1. 等待用户授权明确到期。
        2. 重放旧报文并发送同授权的新标识请求。

    预期结果：
        1. 旧请求和新请求均不得读取资源。
        2. 报文去重不能代替授权有效性检查。
    """

    def test_expired_user_authorization_replay_and_new_request(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不能捕获或重放产品入站报文、签发可到期的最终用户授权或构造同授权新请求标识，也没有权威授权和后端访问 Provider。")
