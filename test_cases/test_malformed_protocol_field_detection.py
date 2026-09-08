"""Verify malformed protocol fields are rejected before business logic."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D2-02-S01-05"
TEST_SAMPLE_ID = "ATS-6.2f-D2-02-S01"
TEST_PROMPT_ID = "05"


class TestATS62FD202S0105MalformedProtocolFieldDetection(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D2-02-S01-05

    测试用例名称：畸形协议字段的请求检测

    测试目标：
        验证类型错误的业务字段在协议校验阶段被拒绝。

    前置条件：
        1. 真实入站协议、有效调用凭据和用户授权已就绪。
        2. 协议定义、检测日志和资源访问可核对。

    测试步骤：
        1. 建立合法协议请求成功基线。
        2. 将对象型业务参数改为字符串后提交请求。

    预期结果：
        1. 请求在协议校验阶段被拒且不进入业务。
        2. 安全日志关联调用方和字段类型原因。
    """

    def test_malformed_protocol_field_detection(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不暴露产品入站协议模式或业务字段级请求生成器，不能在保持真实鉴别授权时变更字段类型，也没有协议校验阶段和安全日志 Provider。")
