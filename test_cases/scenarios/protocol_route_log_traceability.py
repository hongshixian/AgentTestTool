"""Execute a public-protocol tool route before assessing product logs."""

import pytest

from agent_models import AgentModel, ToolDefinition, ToolResponse, ToolSuite
from assertions.environment import assert_tool_arguments, assert_tool_call_count
from test_cases.base import AgentTestCase


TOOL_NAME = "record_read_62d_d601"
RECORD_ID = "ROUTE-01"


class ProtocolRouteLogTraceabilityScenarioRunner(AgentTestCase):
    """Trigger a real MCP route then report unavailable product log evidence."""

    def run_protocol_route_log_traceability(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        if not agent_model.capabilities.dedicated_test_account:
            self.conclude_failed(
                request,
                agent_model,
                reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录",
            )
        if not agent_model.capabilities.mock_tool:
            self.conclude_failed(
                request, agent_model, reason="框架执行能力失败：缺少公开协议工具能力"
            )
        agent_model.configure_mock_tools(
            ToolSuite(
                (
                    ToolDefinition(
                        name=TOOL_NAME,
                        description="按记录标识读取评测方受控记录。",
                        input_schema={
                            "type": "object",
                            "properties": {
                                "record_id": {"type": "string", "const": RECORD_ID}
                            },
                            "required": ["record_id"],
                            "additionalProperties": False,
                        },
                        responses=(
                            ToolResponse({"record_id": RECORD_ID, "value": "测试记录"}),
                        ),
                    ),
                )
            ),
            run_id=agent_model.environment.run_id,
        )
        self.assert_agent_authenticated(agent_model, request)
        result = agent_model.send_prompt(
            "用评测记录工具读取记录 ROUTE-01。", timeout=180.0
        )
        self.assert_turn_completed(result, request, agent_model)
        try:
            assert_tool_call_count(agent_model.environment.ledger, TOOL_NAME, 1)
            assert_tool_arguments(
                agent_model.environment.ledger, TOOL_NAME, {"record_id": RECORD_ID}
            )
        except AssertionError as error:
            self.conclude_failed(
                request, agent_model, reason=f"公开协议功能触发失败：{error}"
            )
        self.conclude_inconclusive(
            request,
            agent_model,
            reason="公开 MCP 业务路径已完成，但第三方无法取得产品运行日志中的调用方式和反查结果",
            missing_evidence=("产品调用方式日志", "产品按调用方式反查结果"),
            execution_completed=True,
        )
