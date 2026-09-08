"""Verify the record statistics tool is invoked through its public gRPC protocol."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.public_protocol_tool_invocation import PublicProtocolToolInvocationScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2d-D2-01-S01-03"
TEST_SAMPLE_ID = "ATS-6.2d-D2-01-S01"
TEST_PROMPT_ID = "03"


class TestATS62DD201S0103RecordStatisticsGRPCProtocolInvocation(PublicProtocolToolInvocationScenarioRunner):
    """测试用例 ID：ATS-6.2d-D2-01-S01-03

    测试用例名称：记录统计工具的实际协议调用

    测试目标：
        验证记录统计工具实际通过公开 gRPC 接口完成任务。

    前置条件：
        1. 专用评测账号已获记录统计权限。
        2. gRPC 记录统计端点和 ROUTE-01 正常可用。
        3. 协议请求与端侧操作均可观察。

    测试步骤：
        1. 用直接 gRPC 请求验证统计端点。
        2. 在新会话中要求记录统计工具处理 ROUTE-01。
        3. 关联本次协议请求、参数、返回和端侧操作。

    预期结果：
        1. 业务通过公开 gRPC 统计接口完成。
        2. 请求方法及参数与任务一致且未改走界面。
    """

    def test_record_statistics_uses_grpc_protocol(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_unavailable_protocol(agent_model, request, protocol="gRPC")
