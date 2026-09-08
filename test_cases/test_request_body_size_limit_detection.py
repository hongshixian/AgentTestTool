"""Verify oversized protocol request bodies are rejected before business logic."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D2-02-S01-01"
TEST_SAMPLE_ID = "ATS-6.2f-D2-02-S01"
TEST_PROMPT_ID = "01"


class TestATS62FD202S0101RequestBodySizeLimitDetection(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D2-02-S01-01

    测试用例名称：请求体大小的请求检测

    测试目标：
        验证超过产品请求体上限的协议请求在业务前被拒绝。

    前置条件：
        1. 真实入站协议、有效调用凭据和用户授权已就绪。
        2. 当前请求体边界、请求检测日志和资源访问可核对。

    测试步骤：
        1. 建立边界内资源读取成功基线。
        2. 发送请求体大小为上限加一字节的同类请求。

    预期结果：
        1. 请求被大小检查拒绝且不进入业务。
        2. 安全日志关联调用方和具体拒绝原因。
    """

    def test_request_body_size_limit_detection(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 将 CLI 作为被测客户端，不暴露产品入站请求生成器、真实请求体大小上限或有效调用方与用户授权字段，也没有请求检测日志和后端访问 Provider。")
