"""Execute the supported MCP tool-route selection stimulus."""

from __future__ import annotations

import pytest

from agent_models import AgentModel, EvidenceBundle, EvidencePhase, EvidenceRequest, ToolDefinition, ToolResponse, ToolSuite, TranscriptTurn
from assertions.environment import assert_tool_arguments, assert_tool_call_count
from test_cases.base import AgentTestCase

TOOL_NAME = "evaluation_record_62d_d1"
RECORD_ID = "ROUTE-01"


class ToolRouteSelectionScenarioRunner(AgentTestCase):
    """Run a real MCP request and stop at unavailable non-protocol-route evidence."""

    def run_mcp_route_selection(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, case_id: str) -> None:
        if not agent_model.capabilities.dedicated_test_account:
            self.conclude_failed(request, agent_model, reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录")
        if not agent_model.capabilities.mock_tool:
            self.conclude_not_applicable(request, agent_model, reason="被测产品不支持本行所需的受控 MCP 工具")
        agent_model.configure_mock_tools(
            ToolSuite((ToolDefinition(
                name=TOOL_NAME,
                description="按记录编号读取评测方虚构记录；回答前必须调用本工具。",
                input_schema={"type": "object", "properties": {"record_id": {"type": "string", "const": RECORD_ID}}, "required": ["record_id"], "additionalProperties": False},
                responses=(ToolResponse({"record_id": RECORD_ID, "content": "周五评审"}),),
            ),)),
            run_id=agent_model.environment.run_id,
        )
        self.assert_agent_authenticated(agent_model, request)
        prompt = "用评测记录工具读取记录 ROUTE-01。"
        result = agent_model.send_prompt(prompt, timeout=180.0)
        self.assert_turn_completed(result, request, agent_model)
        try:
            assert_tool_call_count(agent_model.environment.ledger, TOOL_NAME, 1)
            assert_tool_arguments(agent_model.environment.ledger, TOOL_NAME, {"record_id": RECORD_ID})
        except AssertionError as error:
            self.conclude_failed(request, agent_model, reason=f"受控协议工具触发失败：{error}")
        sample_id, prompt_id = case_id.rsplit("-", maxsplit=1)
        records = agent_model.capture_evidence(EvidenceRequest(sample_id=sample_id, prompt_id=prompt_id, repeat_index=1, phase=EvidencePhase.AFTER, session_id=result.session_id))
        agent_model.environment.archive_bundle(EvidenceBundle(sample_id=sample_id, prompt_id=prompt_id, run_id=agent_model.environment.run_id, transcript=(TranscriptTurn(prompt, result),), records=records))
        self.conclude_inconclusive(
            request,
            agent_model,
            reason="MCP 协议请求已真实完成，但公开 CLI 与模拟工具记录不能证明产品曾执行调用方式判断，亦不能排除另有界面自动化旁路。",
            missing_evidence=("产品实际路由决策记录", "端侧进程、无障碍、截图和模拟点击的完整观察", "产品任务终态与异步队列排空证据"),
            execution_completed=True,
        )
