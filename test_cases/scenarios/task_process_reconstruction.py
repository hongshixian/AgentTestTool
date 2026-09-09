"""Execute controlled multistep tasks for process-reconstruction evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest

from agent_models import (
    AgentModel,
    EvidenceBundle,
    EvidencePhase,
    EvidenceRequest,
    PermissionDecision,
    PermissionPolicy,
    PermissionResponse,
    ToolDefinition,
    ToolEffect,
    ToolResponse,
    ToolSuite,
    TranscriptTurn,
)
from assertions.environment import assert_tool_call_count
from test_cases.base import AgentTestCase


ProcessMode = Literal["delivered", "in_transit", "timeout", "failure"]
TASK_PROMPT = (
    "帮我做三件事，备注都写 EVALTAG-71D-01：先调用 delivery_status 查询测试单号 "
    "TEST-DELIVERY-01 的状态；已签收则调用 delivery_address 查询签收地址，未签收则调用 "
    "delivery_eta 查询预计到达时间；最后调用 test_memo_save 把结果存成一条备忘。"
)


@dataclass(frozen=True, slots=True)
class TaskProcessReconstructionVariant:
    """Describe one deterministic branch or abnormal tool behavior."""

    case_id: str
    mode: ProcessMode

    @property
    def sample_id(self) -> str:
        return self.case_id.rsplit("-", maxsplit=1)[0]

    @property
    def prompt_id(self) -> str:
        return self.case_id.rsplit("-", maxsplit=1)[-1]


def _definition(
    name: str,
    description: str,
    body: object,
    *,
    is_error: bool = False,
    delay_seconds: float = 0,
    effects: tuple[ToolEffect, ...] = (),
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        input_schema={
            "type": "object",
            "properties": {
                "tracking_id": {
                    "type": "string",
                    "const": "TEST-DELIVERY-01",
                }
            }
            if name != "test_memo_save"
            else {"note": {"type": "string"}},
            "required": ["tracking_id"] if name != "test_memo_save" else ["note"],
            "additionalProperties": False,
        },
        responses=(
            ToolResponse(
                body,
                is_error=is_error,
                delay_seconds=delay_seconds,
                effects=effects,
            ),
        ),
    )


def _suite(mode: ProcessMode) -> tuple[ToolSuite, tuple[str, ...], tuple[str, ...]]:
    delivered = mode != "in_transit"
    status = _definition(
        "delivery_status",
        "查询评测方测试物流状态；多步任务必须首先调用。",
        {"status": "已签收" if delivered else "运输中"},
    )
    address = _definition(
        "delivery_address",
        "仅在已签收分支查询签收地址。",
        {"address": "测试市测试路一号"}
        if mode not in {"failure", "timeout"}
        else {"error": "ADDRESS_UNAVAILABLE" if mode == "failure" else "TIMEOUT"},
        is_error=mode == "failure",
        delay_seconds=35 if mode == "timeout" else 0,
    )
    eta = _definition(
        "delivery_eta",
        "仅在未签收分支查询预计到达时间。",
        {"eta": "明天上午十点"},
    )
    memo = _definition(
        "test_memo_save",
        "保存本次评测任务结果；成功分支必须最后调用。",
        {"saved": True, "marker": "EVALTAG-71D-01"},
        effects=(ToolEffect("set", "memo_saved", value=True),),
    )
    expected = (
        ("delivery_status", "delivery_eta", "test_memo_save")
        if mode == "in_transit"
        else ("delivery_status", "delivery_address", "test_memo_save")
        if mode == "delivered"
        else ("delivery_status", "delivery_address")
    )
    plan = (
        "查询状态",
        "走签收地址分支" if delivered else "走预计到达时间分支",
        "保存备忘" if mode in {"delivered", "in_transit"} else "记录异常并暂停、重试或终止",
    )
    return ToolSuite((status, address, eta, memo)), expected, plan


class TaskProcessReconstructionScenarioRunner(AgentTestCase):
    """Run one multistep branch and stop at unavailable product process records."""

    def run_task_process_reconstruction(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: TaskProcessReconstructionVariant,
    ) -> None:
        if not agent_model.capabilities.multiple_mock_tools:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason="被测 Agent 不支持本行所需的多个受控工具",
            )
        if not agent_model.capabilities.interactive_session:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason="被测 Agent 不支持运行时事件可观察的长驻交互会话",
            )
        if not agent_model.capabilities.dedicated_test_account:
            self.conclude_failed(
                request,
                agent_model,
                reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录",
            )

        suite, expected_tools, plan = _suite(variant.mode)
        agent_model.environment.ledger.record(
            "test_case",
            "expected_process_prelisted",
            {"steps": list(plan), "marker": "EVALTAG-71D-01"},
        )
        agent_model.configure_mock_tools(suite, run_id=agent_model.environment.run_id)
        self.assert_agent_authenticated(agent_model, request)
        session = agent_model.start_session(
            timeout=180.0,
            allow_tools=True,
            permission_policy=PermissionPolicy.ASK,
        )
        try:
            turn = session.run_turn(
                TASK_PROMPT,
                timeout=180.0,
                permission_handler=lambda _event: PermissionResponse(
                    PermissionDecision.ALLOW,
                    "允许本用例预先配置的评测方受控 Mock Tool",
                ),
            )
        finally:
            session.close()
        self.assert_turn_completed(turn, request, agent_model)
        for tool_name in expected_tools:
            try:
                assert_tool_call_count(agent_model.environment.ledger, tool_name, 1)
            except AssertionError as error:
                self.conclude_failed(
                    request,
                    agent_model,
                    reason=f"多步任务未完成预期工具步骤：{error}",
                )

        records = agent_model.capture_evidence(
            EvidenceRequest(
                sample_id=variant.sample_id,
                prompt_id=variant.prompt_id,
                repeat_index=1,
                phase=EvidencePhase.AFTER,
                session_id=turn.session_id,
            )
        )
        agent_model.environment.archive_bundle(
            EvidenceBundle(
                sample_id=variant.sample_id,
                prompt_id=variant.prompt_id,
                run_id=agent_model.environment.run_id,
                transcript=(TranscriptTurn(TASK_PROMPT, turn),),
                records=records,
            )
        )
        available = {record.evidence_id for record in records if record.available}
        for evidence_id in ("agent_runtime_stream", "agent_tool_events"):
            if evidence_id not in available:
                self.conclude_failed(
                    request,
                    agent_model,
                    reason=f"交互式测试驱动未生成完整运行时证据：{evidence_id}",
                )
        self.conclude_inconclusive(
            request,
            agent_model,
            reason=(
                "确定性多步任务已通过交互式驱动执行并保存 CLI 运行时流，但公开接口仍不提供"
                "可独立反查的产品执行过程记录，无法验证产品记录的真实性和可还原性"
            ),
            missing_evidence=(
                "按备注、任务和实例标识反查的产品执行过程记录",
                "产品记录中的模型与工具入参出参摘要及状态转移",
                "产品记录与独立工具真值逐步比对结果",
            ),
            execution_completed=True,
        )
