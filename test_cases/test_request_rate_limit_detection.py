"""Verify excessive protocol request rates are limited before business execution."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D2-02-S01-03"
TEST_SAMPLE_ID = "ATS-6.2f-D2-02-S01"
TEST_PROMPT_ID = "03"


class TestATS62FD202S0103RequestRateLimitDetection(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D2-02-S01-03

    测试用例名称：请求频率的请求检测

    测试目标：
        验证超过产品当前计量窗口频率上限的请求被限流。

    前置条件：
        1. 真实入站协议、有效调用凭据和用户授权已就绪。
        2. 当前频率边界、计量窗口和资源访问可核对。

    测试步骤：
        1. 建立频率上限内成功基线。
        2. 在同一窗口按高于上限的速率发送独立请求。

    预期结果：
        1. 超限部分被限流且业务数不超过额度。
        2. 安全日志关联调用方和限流原因。
    """

    def test_request_rate_limit_detection(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="测试侧可并发启动 CLI，但当前 AgentModel 不暴露产品入站调用方计量窗口、真实速率边界或协议请求生成器，也没有产品限流日志和后端业务计数 Provider。")
