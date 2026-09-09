"""Black-box observation adapter for CodeBuddy E2E tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from agent_models.evidence import (
    EvidenceAuthority,
    EvidenceCorrelation,
    EvidenceRecord,
    EvidenceRequest,
    EvidenceSource,
    EvidenceStatus,
    JsonValue,
)
from agent_models.interaction import AgentEvent, AgentEventType
from configs.environment import agent_process_environment


_STREAM_LIMITATIONS = (
    "仅证明当前 CodeBuddy CLI 进程通过公开 stream-json 通道发出的运行时事件。",
    "不证明云端账号身份、服务端授权状态、安全审计事件或未观察通道中不存在副作用。",
    "标准输出与标准错误跨管道的先后顺序仅代表测试侧观察顺序，不代表产品因果顺序。",
)


class CodeBuddyCommandEvidenceProvider:
    """Collect externally observable evidence through a configured helper."""

    def __init__(
        self,
        *,
        workspace: Path,
        command: Sequence[str] = (),
        default_timeout: float = 30.0,
    ) -> None:
        self.workspace = workspace
        self.command = tuple(command)
        self.default_timeout = default_timeout

    @classmethod
    def from_environment(cls, *, workspace: Path) -> CodeBuddyCommandEvidenceProvider:
        raw_command = os.environ.get("CODEBUDDY_OBSERVATION_COMMAND", "").strip()
        if not raw_command:
            return cls(workspace=workspace)
        try:
            parsed = json.loads(raw_command)
        except json.JSONDecodeError as error:
            raise ValueError("CODEBUDDY_OBSERVATION_COMMAND 必须是 JSON 字符串数组") from error
        if not isinstance(parsed, list) or not parsed or not all(
            isinstance(item, str) and item for item in parsed
        ):
            raise ValueError("CODEBUDDY_OBSERVATION_COMMAND 必须是非空 JSON 字符串数组")
        try:
            timeout = float(os.environ.get("CODEBUDDY_OBSERVATION_TIMEOUT", "30"))
        except ValueError as error:
            raise ValueError("CODEBUDDY_OBSERVATION_TIMEOUT 必须是数字") from error
        if timeout <= 0:
            raise ValueError("CODEBUDDY_OBSERVATION_TIMEOUT 必须大于 0")
        return cls(workspace=workspace, command=parsed, default_timeout=timeout)

    def is_available(self) -> bool:
        if not self.command:
            return False
        executable = self.command[0]
        path = Path(executable).expanduser()
        if path.is_absolute() or path.parent != Path("."):
            return path.is_file()
        return shutil.which(executable) is not None

    def capture(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        if not self.is_available():
            raise RuntimeError("CodeBuddy 黑盒观察命令未配置或不可执行")

        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(request.provider_payload(), ensure_ascii=False) + "\n",
                cwd=self.workspace,
                env=agent_process_environment(),
                capture_output=True,
                check=False,
                text=True,
                timeout=self.default_timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("CodeBuddy 黑盒观察命令执行超时") from error
        if completed.returncode != 0:
            raise RuntimeError(
                f"CodeBuddy 黑盒观察命令失败（退出码 {completed.returncode}）"
            )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("CodeBuddy 黑盒观察命令未返回有效 JSON") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("evidence"), list):
            raise RuntimeError("CodeBuddy 黑盒观察命令返回值必须包含 evidence 数组")

        records: list[EvidenceRecord] = []
        for item in payload["evidence"]:
            if not isinstance(item, dict):
                raise RuntimeError("CodeBuddy 黑盒观察记录必须是 JSON 对象")
            evidence_id = item.get("evidence_id")
            evidence_type = item.get("type")
            if not isinstance(evidence_id, str) or not evidence_id:
                raise RuntimeError("CodeBuddy 黑盒观察记录缺少 evidence_id")
            if not isinstance(evidence_type, str) or not evidence_type:
                raise RuntimeError("CodeBuddy 黑盒观察记录缺少 type")
            status = _evidence_status(item.get("status"))
            source = _evidence_source(item.get("source"))
            correlation = _command_correlation(item.get("correlation"), request)
            records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    evidence_type=evidence_type,
                    phase=request.phase,
                    data=cast(JsonValue, item.get("data")),
                    status=status,
                    source=source,
                    correlation=correlation,
                    proves=_string_tuple(
                        item.get("proves"),
                        default=("由配置的第三方黑盒观察命令返回的事实",),
                    ),
                    limitations=_string_tuple(
                        item.get("limitations"),
                        default=(
                            "证据权威性受配置命令所查询的公开入口及其权限范围限制。",
                        ),
                    ),
                )
            )
        return tuple(records)


class CodeBuddyStreamEvidenceAdapter:
    """Convert normalized CodeBuddy stream events into bounded evidence claims."""

    def capture(
        self,
        request: EvidenceRequest,
        *,
        events: Sequence[AgentEvent],
        run_id: str,
        product_version: str | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        selected = tuple(
            event
            for event in events
            if request.session_id is None or event.session_id in {None, request.session_id}
        )
        started = any(
            event.event_type is AgentEventType.SESSION_STARTED for event in selected
        )
        terminal = any(
            event.event_type is AgentEventType.TURN_COMPLETED for event in selected
        )
        if not selected:
            status = EvidenceStatus.MISSING
        elif started and terminal:
            status = EvidenceStatus.AVAILABLE
        else:
            status = EvidenceStatus.UNVERIFIED

        source = EvidenceSource(
            provider="codebuddy_stream_json",
            channel="stdio_stream_json",
            authority=EvidenceAuthority.PRODUCT_RUNTIME,
            product="codebuddy",
            product_version=product_version,
            observed_at=selected[-1].observed_at if selected else None,
        )
        correlation = _event_correlation(selected, run_id=run_id)
        window = {
            "first_sequence": selected[0].sequence if selected else None,
            "last_sequence": selected[-1].sequence if selected else None,
            "session_started": started,
            "turn_terminal_observed": terminal,
            "session_exit_observed": any(
                event.event_type is AgentEventType.SESSION_EXITED for event in selected
            ),
        }
        records: list[EvidenceRecord] = [
            EvidenceRecord(
                evidence_id="agent_runtime_stream",
                evidence_type="runtime_evidence",
                phase=request.phase,
                data={
                    "observation_window": window,
                    "events": [_event_payload(event) for event in selected],
                },
                status=status,
                source=source,
                correlation=correlation,
                proves=(
                    "当前 CLI 会话在观察窗口内发出的会话、输出和终态事件",
                    "事件中公开的会话、请求、工具、权限和任务关联标识",
                ),
                limitations=_STREAM_LIMITATIONS,
            )
        ]
        categories = (
            (
                "agent_session_correlation",
                {
                    AgentEventType.SESSION_STARTED,
                    AgentEventType.USER_INPUT,
                    AgentEventType.TURN_COMPLETED,
                    AgentEventType.SESSION_EXITED,
                },
                ("CLI 会话、测试输入和回合终态之间的公开标识关联",),
            ),
            (
                "agent_tool_events",
                {AgentEventType.TOOL_CALL, AgentEventType.TOOL_RESULT},
                ("当前 CLI 运行时公开的工具调用及工具结果",),
            ),
            (
                "agent_permission_events",
                {
                    AgentEventType.PERMISSION_REQUEST,
                    AgentEventType.PERMISSION_DECISION,
                },
                ("当前 CLI 权限请求及测试驱动发送的对应决定",),
            ),
            (
                "agent_runtime_control",
                {AgentEventType.CONTROL_REQUEST, AgentEventType.CONTROL_RESPONSE},
                ("测试驱动发送的运行中控制请求及 CLI 返回的公开响应",),
            ),
            (
                "agent_task_events",
                {
                    AgentEventType.TASK_STARTED,
                    AgentEventType.TASK_PROGRESS,
                    AgentEventType.TASK_UPDATED,
                    AgentEventType.TASK_COMPLETED,
                    AgentEventType.TASK_FAILED,
                    AgentEventType.TASK_CANCELLED,
                },
                ("当前 CLI 运行时公开的后台任务生命周期事件",),
            ),
        )
        for evidence_id, event_types, proves in categories:
            matching = tuple(
                event for event in selected if event.event_type in event_types
            )
            if not matching:
                continue
            records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    evidence_type="runtime_evidence",
                    phase=request.phase,
                    data={
                        "observation_window": window,
                        "events": [_event_payload(event) for event in matching],
                    },
                    status=status,
                    source=source,
                    correlation=correlation,
                    proves=proves,
                    limitations=_STREAM_LIMITATIONS,
                )
            )
        return tuple(records)


def _event_payload(event: AgentEvent) -> dict[str, JsonValue]:
    return {
        "sequence": event.sequence,
        "event_type": event.event_type.value,
        "observed_at": event.observed_at,
        "monotonic_seconds": event.monotonic_seconds,
        "session_id": event.session_id,
        "request_id": event.request_id,
        "turn_id": event.turn_id,
        "text": event.text,
        "data": event.data,
    }


def _event_correlation(
    events: Sequence[AgentEvent], *, run_id: str
) -> EvidenceCorrelation:
    task_ids: list[str] = []
    tool_use_ids: list[str] = []
    for event in events:
        if not isinstance(event.data, dict):
            continue
        task = event.data.get("task_id") or event.data.get("taskId")
        tool = (
            event.data.get("tool_use_id")
            or event.data.get("toolUseId")
            or (
                event.data.get("id")
                if event.event_type is AgentEventType.TOOL_CALL
                else None
            )
        )
        if isinstance(task, str):
            task_ids.append(task)
        if isinstance(tool, str):
            tool_use_ids.append(tool)
    return EvidenceCorrelation(
        run_id=run_id,
        session_ids=_unique(event.session_id for event in events),
        request_ids=_unique(event.request_id for event in events),
        turn_ids=_unique(event.turn_id for event in events),
        task_ids=_unique(task_ids),
        tool_use_ids=_unique(tool_use_ids),
    )


def _unique(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if isinstance(value, str)))


def _evidence_status(value: object) -> EvidenceStatus:
    if value is None:
        return EvidenceStatus.AVAILABLE
    try:
        return EvidenceStatus(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError("CodeBuddy 黑盒观察记录包含无效 status") from error


def _evidence_source(value: object) -> EvidenceSource:
    observed_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    if value is None:
        return EvidenceSource(
            provider="codebuddy_configured_observation",
            channel="configured_public_command",
            authority=EvidenceAuthority.EVALUATOR_OBSERVED,
            product="codebuddy",
            observed_at=observed_at,
        )
    if not isinstance(value, dict):
        raise RuntimeError("CodeBuddy 黑盒观察记录的 source 必须是 JSON 对象")
    provider = value.get("provider")
    channel = value.get("channel")
    if not isinstance(provider, str) or not provider.strip():
        raise RuntimeError("CodeBuddy 黑盒观察记录的 source 缺少 provider")
    if not isinstance(channel, str) or not channel.strip():
        raise RuntimeError("CodeBuddy 黑盒观察记录的 source 缺少 channel")
    try:
        authority = EvidenceAuthority(value.get("authority", "unknown"))
    except (TypeError, ValueError) as error:
        raise RuntimeError("CodeBuddy 黑盒观察记录包含无效 authority") from error
    product = value.get("product", "codebuddy")
    product_version = value.get("product_version")
    source_observed_at = value.get("observed_at", observed_at)
    for name, item in (
        ("product", product),
        ("product_version", product_version),
        ("observed_at", source_observed_at),
    ):
        if item is not None and not isinstance(item, str):
            raise RuntimeError(f"CodeBuddy 黑盒观察记录的 source.{name} 必须是字符串")
    return EvidenceSource(
        provider=provider,
        channel=channel,
        authority=authority,
        product=product,
        product_version=product_version,
        observed_at=source_observed_at,
    )


def _command_correlation(
    value: object, request: EvidenceRequest
) -> EvidenceCorrelation:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise RuntimeError("CodeBuddy 黑盒观察记录的 correlation 必须是 JSON 对象")
    run_id = value.get("run_id") or (
        request.context.run_id if request.context is not None else None
    )
    if run_id is not None and not isinstance(run_id, str):
        raise RuntimeError("CodeBuddy 黑盒观察记录的 correlation.run_id 必须是字符串")
    sessions = _string_tuple(value.get("session_ids"))
    if request.session_id:
        sessions = _unique((request.session_id, *sessions))
    return EvidenceCorrelation(
        run_id=run_id,
        session_ids=sessions,
        request_ids=_string_tuple(value.get("request_ids")),
        turn_ids=_string_tuple(value.get("turn_ids")),
        task_ids=_string_tuple(value.get("task_ids")),
        tool_use_ids=_string_tuple(value.get("tool_use_ids")),
    )


def _string_tuple(
    value: object,
    *,
    default: tuple[str, ...] = (),
) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise RuntimeError("CodeBuddy 黑盒观察记录的列表字段必须只包含非空字符串")
    return _unique(value)
