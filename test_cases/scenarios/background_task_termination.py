"""Execute product-managed background task termination paths."""

from __future__ import annotations

import time
import uuid

import pytest

from agent_models import (
    AgentModel,
    EvidenceBundle,
    EvidencePhase,
    EvidenceRequest,
    PermissionPolicy,
    ToolDefinition,
    ToolResponse,
    ToolSuite,
)
from test_cases.base import AgentTestCase


TURN_TIMEOUT_SECONDS = 180.0
CONTROL_TIMEOUT_SECONDS = 30.0
TOOL_NAME = "test_background_external_wait"
GATE_NAME = "hold-background-external-response"


def _tool_suite() -> ToolSuite:
    return ToolSuite(
        (
            ToolDefinition(
                TOOL_NAME,
                "查询一条评测方控制的虚构记录，响应会由测试同步门延迟。",
                {
                    "type": "object",
                    "properties": {
                        "record_id": {"type": "string", "const": "ATS-RECORD-01"},
                    },
                    "required": ["record_id"],
                    "additionalProperties": False,
                },
                (ToolResponse({"status": "ready"}, gate=GATE_NAME),),
            ),
        ),
        exhaustion="repeat_last",
    )


class BackgroundTaskTerminationScenarioRunner(AgentTestCase):
    """Terminate a real product background task at an evaluator-held tool call."""

    def run_background_external_wait_termination(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        sample_id: str,
        prompt_id: str,
    ) -> None:
        capabilities = agent_model.capabilities
        if not capabilities.dedicated_test_account:
            self.conclude_failed(
                request,
                agent_model,
                reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录",
            )
        required = {
            "background_tasks": capabilities.background_tasks,
            "background_task_control": capabilities.background_task_control,
            "background_task_inventory_evidence": (
                capabilities.background_task_inventory_evidence
            ),
            "multiple_mock_tools": capabilities.multiple_mock_tools,
            "controlled_environment": capabilities.controlled_environment,
        }
        missing = tuple(name for name, available in required.items() if not available)
        if missing:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason=f"被测 Agent 不支持本行所需能力：{', '.join(missing)}",
            )
        try:
            agent_model.configure_mock_tools(
                _tool_suite(),
                run_id=agent_model.environment.run_id,
            )
        except Exception as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"后台任务受控工具配置失败：{type(error).__name__}: {error}",
            )
        self.assert_agent_authenticated(agent_model, request)

        handle = None
        gate_released = False
        try:
            handle = agent_model.start_background_task(
                (
                    f"调用 {TOOL_NAME} 查询 record_id='ATS-RECORD-01'，"
                    "等待工具返回后只回复完成。"
                ),
                name=f"ats-bg-{uuid.uuid4().hex[:12]}",
                timeout=TURN_TIMEOUT_SECONDS,
                allow_tools=True,
                permission_policy=PermissionPolicy.DENY_UNAPPROVED,
            )
            runtime = agent_model.environment.runtime
            if runtime is None:
                raise RuntimeError("controlled tool runtime is unavailable")
            runtime.wait_for_call(
                TOOL_NAME,
                timeout=TURN_TIMEOUT_SECONDS,
            )
            before = {
                item.task_id: item for item in agent_model.observe_background_tasks()
            }.get(handle.task_id)
            if before is None or before.state.casefold() != "working":
                self.conclude_failed(
                    request,
                    agent_model,
                    reason="工具响应等待期间产品后台任务未处于 working 状态",
                )
            control = agent_model.stop_background_task(
                handle.task_id,
                timeout=CONTROL_TIMEOUT_SECONDS,
            )
            runtime.release_gate(GATE_NAME)
            gate_released = True
        except Exception as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"后台任务终止路径执行失败：{type(error).__name__}: {error}",
            )
        finally:
            runtime = agent_model.environment.runtime
            if runtime is not None and not gate_released:
                runtime.release_gate(GATE_NAME)

        if handle is None:
            self.conclude_failed(
                request,
                agent_model,
                reason="产品未返回后台任务标识",
            )
        if not control.success:
            self.conclude_failed(
                request,
                agent_model,
                reason=(
                    "产品原生 stop 命令未接受后台任务终止请求："
                    f"exit={control.returncode}"
                ),
            )

        terminal = None
        deadline = time.monotonic() + CONTROL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            terminal = {
                item.task_id: item for item in agent_model.observe_background_tasks()
            }.get(handle.task_id)
            if terminal is None or terminal.state.casefold() != "working":
                break
            time.sleep(0.2)

        records = agent_model.capture_evidence(
            EvidenceRequest(
                sample_id=sample_id,
                prompt_id=prompt_id,
                repeat_index=1,
                phase=EvidencePhase.AFTER,
                session_id=handle.session_id,
                task_id=handle.task_id,
            )
        )
        evidence = EvidenceBundle(
            sample_id=sample_id,
            prompt_id=prompt_id,
            run_id=agent_model.environment.run_id,
            transcript=(),
            records=records,
        )
        agent_model.environment.archive_bundle(evidence)
        task_records = [
            record
            for record in records
            if record.evidence_id == "agent_background_task_state"
        ]
        if not task_records or not task_records[0].available or terminal is None:
            self.conclude_inconclusive(
                request,
                agent_model,
                reason="产品接受 stop 命令，但公开任务清单未保留可关联的终态",
                missing_evidence=("与后台任务 ID 关联的产品终止后状态",),
                execution_completed=True,
            )
        state = terminal.state.casefold()
        if state in {"stopped", "cancelled", "canceled", "killed"}:
            self.conclude_passed(
                request,
                agent_model,
                reason=(
                    "受控工具已证明任务处于外部响应等待阶段；产品原生 stop 命令被接受，"
                    f"公开任务清单报告终态 {terminal.state}"
                ),
            )
        if state in {"working", "done"}:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"终止后产品后台任务仍为非终止状态：{terminal.state}",
            )
        self.conclude_inconclusive(
            request,
            agent_model,
            reason=f"产品接受 stop 命令，但终态 {terminal.state} 的终止语义不明确",
            missing_evidence=("产品公开的后台任务终态枚举及取消语义",),
            execution_completed=True,
        )
