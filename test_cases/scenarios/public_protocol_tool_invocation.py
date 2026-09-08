"""Execute or classify public-protocol tool invocation paths."""

import pytest

from agent_models import AgentModel, ToolDefinition, ToolResponse, ToolSuite
from assertions.environment import assert_tool_arguments, assert_tool_call_count
from test_cases.base import AgentTestCase


MCP_TOOL = "record_search_62d_d2"
RECORD_ID = "ROUTE-01"


class PublicProtocolToolInvocationScenarioRunner(AgentTestCase):
    """Verify supported MCP invocation or reject unsupported protocol transports."""

    def run_unavailable_protocol(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        protocol: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行要求 CodeBuddy 直接把工具作为公开 {protocol} 接口调用并保留协议请求；"
                "当前产品适配器只支持把受控工具接入为 STDIO MCP，不能将 REST 或 gRPC"
                "端点注册为产品原生工具，MCP 代理转发不能替代被测 Agent 的指定协议调用"
            ),
        )

    def run_mcp_protocol(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        if not agent_model.capabilities.dedicated_test_account:
            self.conclude_failed(
                request,
                agent_model,
                reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录",
            )
        if not agent_model.capabilities.mock_tool:
            self.conclude_failed(request, agent_model, reason="框架执行能力失败：缺少受控 MCP 工具能力")
        agent_model.configure_mock_tools(
            ToolSuite(
                (
                    ToolDefinition(
                        name=MCP_TOOL,
                        description="通过 MCP tools/call 检索指定评测记录；回答前必须调用。",
                        input_schema={
                            "type": "object",
                            "properties": {"record_id": {"type": "string", "const": RECORD_ID}},
                            "required": ["record_id"],
                            "additionalProperties": False,
                        },
                        responses=(ToolResponse({"record_id": RECORD_ID, "content": "周五评审"}),),
                    ),
                )
            ),
            run_id=agent_model.environment.run_id,
        )
        self.assert_agent_authenticated(agent_model, request)
        result = agent_model.send_prompt(
            "使用记录检索工具处理评测记录 ROUTE-01，返回处理结果。",
            timeout=180.0,
        )
        self.assert_turn_completed(result, request, agent_model)
        try:
            assert_tool_call_count(agent_model.environment.ledger, MCP_TOOL, 1)
            assert_tool_arguments(agent_model.environment.ledger, MCP_TOOL, {"record_id": RECORD_ID})
            assert "周五" in result.response and "评审" in result.response
        except AssertionError as error:
            self.conclude_failed(request, agent_model, reason=f"MCP 实际调用断言失败：{error}")
        self.conclude_passed(
            request,
            agent_model,
            reason="记录检索通过唯一启用的 STDIO MCP tools/call 通道完成且方法参数和返回一致",
        )
