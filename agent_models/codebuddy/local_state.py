"""Control isolated CodeBuddy local state through a trusted command."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from agent_models.evidence import EvidencePhase, EvidenceRecord, JsonValue
from agent_models.local_state import LocalStateAction, LocalStateRequest


class CodeBuddyCommandLocalStateController:
    def __init__(
        self,
        *,
        workspace: Path,
        command: Sequence[str] = (),
        default_timeout: float = 60.0,
    ) -> None:
        self.workspace = workspace
        self.command = tuple(command)
        self.default_timeout = default_timeout

    @classmethod
    def from_environment(cls, *, workspace: Path) -> CodeBuddyCommandLocalStateController:
        raw_command = os.environ.get("CODEBUDDY_LOCAL_STATE_COMMAND", "").strip()
        if not raw_command:
            return cls(workspace=workspace)
        try:
            parsed = json.loads(raw_command)
        except json.JSONDecodeError as error:
            raise ValueError("CODEBUDDY_LOCAL_STATE_COMMAND 必须是 JSON 字符串数组") from error
        if not isinstance(parsed, list) or not parsed or not all(
            isinstance(item, str) and item for item in parsed
        ):
            raise ValueError("CODEBUDDY_LOCAL_STATE_COMMAND 必须是非空 JSON 字符串数组")
        try:
            timeout = float(os.environ.get("CODEBUDDY_LOCAL_STATE_TIMEOUT", "60"))
        except ValueError as error:
            raise ValueError("CODEBUDDY_LOCAL_STATE_TIMEOUT 必须是数字") from error
        if timeout <= 0:
            raise ValueError("CODEBUDDY_LOCAL_STATE_TIMEOUT 必须大于 0")
        return cls(workspace=workspace, command=parsed, default_timeout=timeout)

    def is_available(self) -> bool:
        if not self.command:
            return False
        executable = self.command[0]
        path = Path(executable).expanduser()
        if path.is_absolute() or path.parent != Path("."):
            return path.is_file()
        return shutil.which(executable) is not None

    def execute(
        self,
        action: LocalStateAction,
        request: LocalStateRequest,
    ) -> tuple[EvidenceRecord, ...]:
        if not self.is_available():
            raise RuntimeError("CodeBuddy 本地状态控制命令未配置或不可执行")
        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(
                    request.provider_payload(action),
                    ensure_ascii=False,
                )
                + "\n",
                cwd=self.workspace,
                env=os.environ.copy(),
                capture_output=True,
                check=False,
                text=True,
                timeout=self.default_timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("CodeBuddy 本地状态控制命令执行超时") from error
        if completed.returncode != 0:
            detail = completed.stderr.strip()
            if request.context.authorization:
                detail = detail.replace(request.context.authorization, "***")
            raise RuntimeError(
                f"CodeBuddy 本地状态控制命令失败（退出码 {completed.returncode}）："
                f"{detail[-500:]}"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("CodeBuddy 本地状态控制命令未返回有效 JSON") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("evidence"), list):
            raise RuntimeError("CodeBuddy 本地状态控制命令返回值必须包含 evidence 数组")

        phase = EvidencePhase.BEFORE if action is LocalStateAction.PREPARE else EvidencePhase.AFTER
        records: list[EvidenceRecord] = []
        for item in payload["evidence"]:
            if not isinstance(item, dict):
                raise RuntimeError("CodeBuddy 本地状态证据记录必须是 JSON 对象")
            evidence_id = item.get("evidence_id")
            evidence_type = item.get("type")
            if not isinstance(evidence_id, str) or not evidence_id:
                raise RuntimeError("CodeBuddy 本地状态证据记录缺少 evidence_id")
            if not isinstance(evidence_type, str) or not evidence_type:
                raise RuntimeError("CodeBuddy 本地状态证据记录缺少 type")
            records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    evidence_type=evidence_type,
                    phase=phase,
                    data=cast(JsonValue, item.get("data")),
                )
            )
        return tuple(records)
