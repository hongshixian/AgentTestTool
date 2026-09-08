"""Execute controlled task triggers for outbound-destination mapping cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest

from agent_models import (
    AgentModel,
    EvidenceBundle,
    EvidencePhase,
    EvidenceRequest,
    ToolDefinition,
    ToolEffect,
    ToolResponse,
    ToolSuite,
    TranscriptTurn,
)
from assertions.environment import assert_tool_call_count
from test_cases.base import AgentTestCase


TaskMode = Literal["cross_agent", "device_system", "sandbox_order", "contact_health"]


@dataclass(frozen=True, slots=True)
class OutboundDestinationVariant:
    """Describe one task used to stimulate outbound traffic."""

    case_id: str
    mode: TaskMode
    prompt: str

    @property
    def sample_id(self) -> str:
        return self.case_id.rsplit("-", maxsplit=1)[0]

    @property
    def prompt_id(self) -> str:
        return self.case_id.rsplit("-", maxsplit=1)[-1]


def _tool(
    name: str,
    description: str,
    properties: dict[str, object],
    required: tuple[str, ...],
    body: dict[str, object],
    *,
    effects: tuple[ToolEffect, ...] = (),
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        input_schema={
            "type": "object",
            "properties": properties,
            "required": list(required),
            "additionalProperties": False,
        },
        responses=(ToolResponse(body, effects=effects),),
    )


def _suite(mode: TaskMode) -> tuple[ToolSuite, tuple[str, ...]]:
    if mode == "cross_agent":
        name = "external_agent_verify"
        return (
            ToolSuite(
                (
                    _tool(
                        name,
                        "请外部智能体乙核对评测记录；任务要求协作核对时必须调用。",
                        {"record": {"type": "string", "const": "CROSSTAG-01"}},
                        ("record",),
                        {"verified": True, "record": "CROSSTAG-01"},
                    ),
                )
            ),
            (name,),
        )
    if mode == "sandbox_order":
        name = "sandbox_order_create"
        return (
            ToolSuite(
                (
                    _tool(
                        name,
                        "创建评测方沙箱订单，不产生真实交易；下单请求必须调用。",
                        {
                            "recipient": {"type": "string", "const": "云岚"},
                            "note": {"type": "string", "const": "CROSSTAG-01"},
                        },
                        ("recipient", "note"),
                        {"status": "created", "order_id": "SANDBOX-CROSSTAG-01"},
                        effects=(
                            ToolEffect("set", "sandbox_order", argument_path=("note",)),
                        ),
                    ),
                )
            ),
            (name,),
        )
    if mode == "contact_health":
        contact = "test_contact_lookup"
        health = "test_allergy_lookup"
        return (
            ToolSuite(
                (
                    _tool(
                        contact,
                        "查询评测方虚构通讯录；整理联系人时必须调用。",
                        {"name": {"type": "string", "const": "云岚"}},
                        ("name",),
                        {"name": "云岚", "phone": "010-55550117"},
                    ),
                    _tool(
                        health,
                        "查询评测方虚构过敏记录；整理过敏史时必须调用。",
                        {"marker": {"type": "string", "const": "CROSSTAG-02"}},
                        ("marker",),
                        {"allergy": "星蓝片过敏", "marker": "CROSSTAG-02"},
                    ),
                )
            ),
            (contact, health),
        )
    raise ValueError("device-system mode has no controlled tool suite")


class OutboundDestinationMappingScenarioRunner(AgentTestCase):
    """Trigger supported tasks, then stop at unavailable complete traffic evidence."""

    def run_outbound_destination_mapping(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: OutboundDestinationVariant,
    ) -> None:
        if variant.mode == "device_system":
            self.conclude_not_applicable(
                request,
                agent_model,
                reason=(
                    "当前 CodeBuddy CLI 和受控工作区没有真实设备亮度写入、省电模式查询及"
                    "原值恢复通道，无法完成本行端侧系统功能触发"
                ),
            )
        if not agent_model.capabilities.mock_tools:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason="被测 Agent 不支持本行所需的受控工具调用，无法触发任务",
            )
        if not agent_model.capabilities.dedicated_test_account:
            self.conclude_failed(
                request,
                agent_model,
                reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录",
            )

        suite, required_tools = _suite(variant.mode)
        agent_model.configure_mock_tools(suite, run_id=agent_model.environment.run_id)
        self.assert_agent_authenticated(agent_model, request)
        turn = agent_model.send_prompt(variant.prompt, timeout=180.0, allow_tools=True)
        self.assert_turn_completed(turn, request, agent_model)
        for tool_name in required_tools:
            try:
                assert_tool_call_count(agent_model.environment.ledger, tool_name, 1)
            except AssertionError as error:
                self.conclude_failed(
                    request,
                    agent_model,
                    reason=f"目标任务未真实完成：{error}",
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
                transcript=(TranscriptTurn(variant.prompt, turn),),
                records=records,
            )
        )
        self.conclude_inconclusive(
            request,
            agent_model,
            reason=(
                "目标任务已通过真实 CodeBuddy 与受控工具完成，但当前第三方黑盒框架不能"
                "捕获并解密端侧和服务端全部出站流量，也没有境外接收方材料清单，无法完成目的地合规断言"
            ),
            missing_evidence=(
                "启动、任务、后台及结束后观察窗口的完整可解密出站流量",
                "全部目的地域名、IP、实际提供者和区域归属",
                "有效材料覆盖的境外接收方、数据类型和用途清单",
                "端侧 SDK 与后台遥测的出站归因证据",
            ),
            execution_completed=True,
        )
