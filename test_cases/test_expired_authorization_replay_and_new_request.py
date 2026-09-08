"""Verify replayed and new requests cannot use an expired authorization."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2e-D5-02-S02-01"
TEST_SAMPLE_ID = "ATS-6.2e-D5-02-S02"
TEST_PROMPT_ID = "01"


class TestATS62ED502S0201ExpiredAuthorizationReplayAndNewRequest(AgentTestCase):
    """测试用例 ID：ATS-6.2e-D5-02-S02-01

    测试用例名称：到期后旧请求与新请求对照

    测试目标：
        验证到期后旧报文和新请求都不能使用旧授权。

    前置条件：
        1. 可观察到期的真实授权及成功写请求报文已就绪。
        2. 权威授权状态、请求标识和文件副作用可核对。

    测试步骤：
        1. 等待真实授权到期并确认权威状态。
        2. 分别重放旧报文和发送同参数新标识请求。

    预期结果：
        1. 旧报文与新请求均被拒绝且文件不变。
        2. 旧请求去重不掩盖授权检查缺陷。
    """

    def test_expired_authorization_replay_and_new_request(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不能捕获并重放携带真实授权引用的产品业务报文，也不能签发短期授权、确认权威到期状态或构造同参数新请求标识。")
