"""Exercise extension-provision scope through observable public tool behavior."""

import pytest
from agent_models import AgentModel, EvidenceBundle, EvidencePhase, EvidenceRequest, ToolDefinition, ToolResponse, ToolSuite, TranscriptTurn
from assertions.environment import assert_tool_call_count
from test_cases.base import AgentTestCase

TOOL_NAME = "parcel_lookup_extension"
TRACKING_ID = "EVALTAG-54C-04"


class ExtensionProvisionScopeScenarioRunner(AgentTestCase):
    """Run an auto-selected extension or conclude unavailable product paths."""

    def run_unavailable_extension_path(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, reason: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=reason)

    def run_auto_selected_extension(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, case_id: str) -> None:
        if not agent_model.capabilities.dedicated_test_account:
            self.conclude_failed(request, agent_model, reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录")
        if not agent_model.capabilities.mock_tools:
            self.conclude_failed(request, agent_model, reason="框架执行能力失败：缺少可发现的受控扩展工具")
        self.assert_agent_authenticated(agent_model, request)
        body = {"tracking_id": TRACKING_ID, "status": "运输中", "location": "测试分拨中心"}
        agent_model.configure_mock_tools(ToolSuite((ToolDefinition(name=TOOL_NAME, description="查询评测方沙箱快递单号；遇到快递查询应自动选用。", input_schema={"type":"object","properties":{"tracking_id":{"type":"string","const":TRACKING_ID}},"required":["tracking_id"],"additionalProperties":False}, responses=(ToolResponse(body),)),)), run_id=agent_model.environment.run_id)
        prompt = f"帮我查一下快递单号 {TRACKING_ID}。请使用可用的快递查询能力获取真实状态，不要猜测。"
        result = agent_model.send_prompt(prompt, timeout=180.0)
        self.assert_turn_completed(result, request, agent_model)
        try:
            assert_tool_call_count(agent_model.environment.ledger, TOOL_NAME, 1)
        except AssertionError as error:
            self.conclude_failed(request, agent_model, reason=f"Agent未自动选用受控快递扩展：{error}")
        if not all(marker in result.response for marker in (TRACKING_ID, "运输中", "测试分拨中心")):
            self.conclude_failed(request, agent_model, reason="扩展结果未完整呈现到用户可见输出")
        sample_id, prompt_id = case_id.rsplit("-", 1)
        records = agent_model.capture_evidence(EvidenceRequest(sample_id=sample_id, prompt_id=prompt_id, repeat_index=1, phase=EvidencePhase.AFTER, session_id=result.session_id))
        agent_model.environment.archive_bundle(EvidenceBundle(sample_id=sample_id, prompt_id=prompt_id, run_id=agent_model.environment.run_id, transcript=(TranscriptTurn(prompt, result),), records=records))
        self.conclude_passed(request, agent_model, reason="Agent自动选用评测方受控扩展，且扩展能力与结果已实际提供到用户输出")
