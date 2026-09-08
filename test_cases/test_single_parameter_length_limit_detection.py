"""Verify oversized protocol parameters are rejected before business logic."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D2-02-S01-02"
TEST_SAMPLE_ID = "ATS-6.2f-D2-02-S01"
TEST_PROMPT_ID = "02"


class TestATS62FD202S0102SingleParameterLengthLimitDetection(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D2-02-S01-02

    测试用例名称：单参数长度的请求检测

    测试目标：
        验证超过单参数长度上限的协议请求在业务前被拒绝。

    前置条件：
        1. 真实入站协议、有效调用凭据和用户授权已就绪。
        2. 当前参数边界、请求检测日志和资源访问可核对。

    测试步骤：
        1. 建立边界内资源读取成功基线。
        2. 将资源参数设为上限加一字符后提交请求。

    预期结果：
        1. 请求被长度检查拒绝且不进入业务。
        2. 安全日志关联调用方和具体拒绝原因。
    """

    def test_single_parameter_length_limit_detection(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不暴露产品入站协议字段、真实单参数长度上限或请求生成器，也没有请求检测阶段、安全日志和后端资源访问 Provider。")
