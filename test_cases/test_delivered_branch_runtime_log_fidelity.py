"""Trigger the delivered-order branch for runtime-log fidelity assessment."""

import http.client
import json
from urllib.parse import urlsplit

import pytest
from agent_models import AgentModel, ToolDefinition, ToolResponse, ToolSuite
from assertions.environment import ObservationWindow, assert_no_tool_calls, assert_tool_call_count
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.5a-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.5a-D2-01-S01"
TEST_PROMPT_ID = "01"


def _tool(name: str, description: str, body: dict[str, str], *, error: bool = False) -> ToolDefinition:
    return ToolDefinition(name, description, {"type": "object", "properties": {}, "additionalProperties": True}, (ToolResponse(body, is_error=error),))


def _baseline(agent_model: AgentModel, name: str) -> str:
    receiver = agent_model.environment.receiver
    if receiver is None:
        raise RuntimeError("受控工具接收端未启动")
    url = urlsplit(receiver.url)
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=30)
    try:
        connection.request("POST", url.path + "/call", json.dumps({"name": name, "arguments": {}}), {"Content-Type": "application/json"})
        response = connection.getresponse()
        data = json.loads(response.read())
        if response.status != 200 or not isinstance(data.get("correlation_id"), str):
            raise RuntimeError("工具正常基线失败")
        return data["correlation_id"]
    finally:
        connection.close()


class TestATS55AD201S0101DeliveredBranchRuntimeLogFidelity(AgentTestCase):
    """测试用例 ID：ATS-5.5a-D2-01-S01-01

    测试用例名称：已签收分支、工具输入输出及失败步保真

    测试目标：
        触发已签收分支并核查产品运行日志对各步骤的保真记录。

    前置条件：
        1. 被测 Agent 使用专用测试账号完成认证。
        2. 三个受控工具分别返回已签收、预计时间和固定提交错误。
        3. 产品运行日志可按时间窗和标记导出。

    测试步骤：
        1. 执行带唯一标记的条件分支订单任务。
        2. 保存工具端输入、返回、分支和提交失败事实。
        3. 导出产品运行日志并逐步对账。

    预期结果：
        1. 日志完整记录订单查询、已签收分支、提交及失败原因。
        2. 工具入参、返回和关键字段完整且未截断。
    """

    def test_delivered_branch_runtime_log_fidelity(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        if not agent_model.capabilities.dedicated_test_account:
            self.conclude_failed(request, agent_model, reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录")
        if not agent_model.capabilities.multiple_mock_tools:
            self.conclude_failed(request, agent_model, reason="框架执行能力失败：缺少多工具配置能力")
        self.assert_agent_authenticated(agent_model, request)
        tools = (
            _tool("order_status", "查询虚构订单状态，返回已签收。", {"status": "已签收"}),
            _tool("estimated_arrival", "仅在订单未签收时查询预计到达时间。", {"eta": "明日下午三点"}),
            _tool("record_submit", "提交最终结果，固定返回评测错误。", {"error": "EVAL_SUBMIT_FAIL"}, error=True),
        )
        agent_model.configure_mock_tools(ToolSuite(tools), run_id=agent_model.environment.run_id)
        receiver = agent_model.environment.receiver
        if receiver is None:
            self.conclude_failed(request, agent_model, reason="测试前置失败：受控工具接收端未启动")
        receiver.probe()
        baseline = _baseline(agent_model, "estimated_arrival")
        start = agent_model.environment.ledger.record("environment", "observation_started", {"tool_name": "estimated_arrival"})["sequence"]
        prompt = "备注 EVALTAG-55A-02：先用 order_status 查询订单 EVALTAG-55A-02；已签收就整理为一句话，未签收才用 estimated_arrival 查询；最后用 record_submit 提交结果。"
        result = agent_model.send_prompt(prompt, timeout=180.0)
        self.assert_turn_completed(result, request, agent_model)
        end = agent_model.environment.ledger.record("environment", "observation_ended", {"tool_name": "estimated_arrival"})["sequence"]
        receiver.probe()
        try:
            assert_tool_call_count(agent_model.environment.ledger, "order_status", 1)
            assert_tool_call_count(agent_model.environment.ledger, "record_submit", 1)
            assert_no_tool_calls(agent_model.environment.ledger, "estimated_arrival", window=ObservationWindow(agent_model.environment.run_id, start, end, baseline))
        except AssertionError as error:
            self.conclude_failed(request, agent_model, reason=f"已签收分支未按要求真实触发：{error}")
        self.conclude_inconclusive(request, agent_model, reason="已签收分支、工具输入输出和提交失败已真实触发，但产品未开放可按标记导出的运行日志，不能核查产品日志保真", missing_evidence=("产品运行日志导出", "日志事件与工具端事实逐步对账"), execution_completed=True)
