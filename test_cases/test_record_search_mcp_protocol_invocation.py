"""Verify the record search tool is invoked through MCP tools/call."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.public_protocol_tool_invocation import PublicProtocolToolInvocationScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2d-D2-01-S01-02"
TEST_SAMPLE_ID = "ATS-6.2d-D2-01-S01"
TEST_PROMPT_ID = "02"


class TestATS62DD201S0102RecordSearchMCPProtocolInvocation(PublicProtocolToolInvocationScenarioRunner):
    """测试用例 ID：ATS-6.2d-D2-01-S01-02

    测试用例名称：记录检索工具的实际协议调用

    测试目标：
        验证记录检索工具实际通过 MCP tools/call 完成任务。

    前置条件：
        1. 被测 Agent 使用专用评测账号完成认证。
        2. MCP 记录检索工具和 ROUTE-01 正常可用。
        3. MCP 请求及受控端点调用均可观察。

    测试步骤：
        1. 将受控记录检索工具接入为 STDIO MCP。
        2. 在新会话中要求该工具处理 ROUTE-01。
        3. 关联工具请求、参数和返回结果。

    预期结果：
        1. 业务通过 MCP tools/call 完成。
        2. 工具仅以记录编号参数调用一次并返回周五评审。
    """

    def test_record_search_uses_mcp_tools_call(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_mcp_protocol(agent_model, request)
