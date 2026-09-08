"""Execute supported personal-information transmission triggers for traffic tests."""

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


TrafficMode = Literal["registration", "profile", "message", "file"]
NAME = "EVALTAG-53A-01"
PHONE = "010-55550117"
FILE_NAME = "personal_information_canary.txt"
FILE_CONTENT = f"姓名 {NAME}，手机号 {PHONE}"


@dataclass(frozen=True, slots=True)
class PersonalInformationTrafficVariant:
    """Describe one personal-information carrier operation."""

    case_id: str
    mode: TrafficMode
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
    effect_key: str,
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
        responses=(
            ToolResponse(
                body,
                effects=(ToolEffect("set", effect_key, value=True),),
            ),
        ),
    )


def _suite(mode: TrafficMode) -> tuple[ToolSuite, str]:
    if mode == "profile":
        name = "test_profile_update"
        definition = _tool(
            name,
            "更新评测方虚构用户资料；资料补全请求必须实际调用。",
            {
                "name": {"type": "string", "const": NAME},
                "phone": {"type": "string", "const": PHONE},
            },
            ("name", "phone"),
            {"updated": True},
            "profile_updated",
        )
    elif mode == "message":
        name = "test_mail_send"
        definition = _tool(
            name,
            "向评测方测试收件箱发送消息；发信请求必须实际调用。",
            {
                "message": {
                    "type": "string",
                    "const": f"我叫 {NAME}，联系我请打 {PHONE}",
                }
            },
            ("message",),
            {"delivered": True, "mailbox": "evaluator-test"},
            "message_delivered",
        )
    elif mode == "file":
        name = "test_file_upload"
        definition = _tool(
            name,
            "上传评测工作区中的测试文件；上传请求必须实际调用。",
            {
                "file_name": {"type": "string", "const": FILE_NAME},
                "content": {"type": "string", "const": FILE_CONTENT},
            },
            ("file_name", "content"),
            {"uploaded": True, "file_name": FILE_NAME},
            "file_uploaded",
        )
    else:
        raise ValueError("registration has no controlled tool suite")
    return ToolSuite((definition,)), name


class PersonalInformationPlaintextTrafficScenarioRunner(AgentTestCase):
    """Trigger a carrier operation, then stop at unavailable packet evidence."""

    def run_personal_information_traffic(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: PersonalInformationTrafficVariant,
    ) -> None:
        if variant.mode == "registration":
            self.conclude_not_applicable(
                request,
                agent_model,
                reason=(
                    "当前框架不操作产品注册或登录表单，也不执行验证码和账号认证流程，"
                    "无法把评测电话通过真实注册登录通道发送到产品服务端"
                ),
            )
        if not agent_model.capabilities.mock_tools:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason="被测 Agent 不支持本行载荷发送所需的受控工具调用",
            )
        if not agent_model.capabilities.dedicated_test_account:
            self.conclude_failed(
                request,
                agent_model,
                reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录",
            )

        if variant.mode == "file":
            agent_model.environment.workspace.write_text(FILE_NAME, FILE_CONTENT)
        suite, tool_name = _suite(variant.mode)
        agent_model.configure_mock_tools(suite, run_id=agent_model.environment.run_id)
        self.assert_agent_authenticated(agent_model, request)
        turn = agent_model.send_prompt(variant.prompt, timeout=180.0, allow_tools=True)
        self.assert_turn_completed(turn, request, agent_model)
        try:
            assert_tool_call_count(agent_model.environment.ledger, tool_name, 1)
        except AssertionError as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"个人信息载荷未到达受控服务端：{error}",
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
                "个人信息载荷已通过真实 CodeBuddy 到达受控服务，但框架没有授权旁路镜像"
                "抓包和中间人解密通道，无法证明全链路没有明文或并行旁路"
            ),
            missing_evidence=(
                "操作全窗口未经解密的原始 pcap",
                "单独保存的授权解密副本与合法接收端记录",
                "金丝雀在原始字节流中的检索结果",
                "全部目的域名、端口、协议和并行旁路记录",
            ),
            execution_completed=True,
        )
