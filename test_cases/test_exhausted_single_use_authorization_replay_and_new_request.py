"""Verify exhausted single-use authorization blocks replayed and new requests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D2-01-S01-09"
TEST_SAMPLE_ID = "ATS-6.2f-D2-01-S01"
TEST_PROMPT_ID = "09"


class TestATS62FD201S0109ExhaustedSingleUseAuthorizationReplayAndNewRequest(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D2-01-S01-09

    测试用例名称：单次额度耗尽后重放与新请求的授权检查

    测试目标：
        验证单次授权耗尽后重放与新请求都不能读取资源。

    前置条件：
        1. 调用方凭据有效且单次用户授权及成功报文已就绪。
        2. 权威授权计数、请求标识和资源访问可关联。

    测试步骤：
        1. 正常读取一次以耗尽单次用户授权。
        2. 重放旧报文并发送同授权的新标识请求。

    预期结果：
        1. 旧请求和新请求均不得再次读取资源。
        2. 报文去重不能代替授权额度检查。
    """

    def test_exhausted_single_use_authorization_replay_and_new_request(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不能捕获或重放产品入站报文、签发并消费单次最终用户授权或构造同授权新请求标识，也没有权威授权计数和后端访问 Provider。")
