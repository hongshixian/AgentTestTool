"""Black-box observation adapter for CodeBuddy E2E tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from agent_models.evidence import EvidenceRecord, EvidenceRequest, JsonValue


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
                env=os.environ.copy(),
                capture_output=True,
                check=False,
                text=True,
                timeout=self.default_timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("CodeBuddy 黑盒观察命令执行超时") from error
        if completed.returncode != 0:
            raise RuntimeError(
                f"CodeBuddy 黑盒观察命令失败（退出码 {completed.returncode}）："
                f"{completed.stderr.strip()[-500:]}"
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
            records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    evidence_type=evidence_type,
                    phase=request.phase,
                    data=cast(JsonValue, item.get("data")),
                )
            )
        return tuple(records)
