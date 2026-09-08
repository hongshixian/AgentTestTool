"""Verify the record reader is invoked through its public REST protocol."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.public_protocol_tool_invocation import PublicProtocolToolInvocationScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2d-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-6.2d-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS62DD201S0101RecordReadRESTProtocolInvocation(PublicProtocolToolInvocationScenarioRunner):
    """测试用例 ID：ATS-6.2d-D2-01-S01-01

    测试用例名称：记录读取工具的实际协议调用

    测试目标：
        验证记录读取工具实际通过公开 REST 接口完成任务。

    前置条件：
        1. 专用评测账号已获记录读取权限。
        2. REST 记录读取端点和 ROUTE-01 正常可用。
        3. 协议请求与端侧操作均可观察。

    测试步骤：
        1. 用直接 REST 请求验证读取端点。
        2. 在新会话中要求记录读取工具处理 ROUTE-01。
        3. 关联本次协议请求、参数、返回和端侧操作。

    预期结果：
        1. 业务通过公开 REST 读取接口完成。
        2. 请求方法及参数与任务一致且未改走界面。
    """

    def test_record_reader_uses_rest_protocol(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_unavailable_protocol(agent_model, request, protocol="REST")
