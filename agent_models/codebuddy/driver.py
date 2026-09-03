"""CodeBuddy commands and JSON output normalization."""

from __future__ import annotations

import json
from typing import Any

from agent_models.result import TurnResult
from agent_models.codebuddy.transport import StdioResponse


class CodeBuddyDriver:
    AUTHENTICATION_PROBE = "这是自动化认证状态检查。请只回复 AUTH_OK。"

    def parse_turn(self, response: StdioResponse) -> TurnResult:
        result_item: dict[str, Any] | None = None
        try:
            payload = json.loads(response.stdout)
            items = payload if isinstance(payload, list) else [payload]
            result_item = next(
                (
                    item
                    for item in reversed(items)
                    if isinstance(item, dict) and item.get("type") == "result"
                ),
                None,
            )
        except json.JSONDecodeError:
            result_item = None

        if result_item is None:
            return TurnResult(
                response="",
                raw_output=response.stdout,
                stderr=response.stderr,
                returncode=response.returncode,
                completed=False,
                duration_seconds=response.duration_seconds,
            )

        text = result_item.get("result")
        completed = (
            response.returncode == 0
            and result_item.get("subtype") == "success"
            and result_item.get("is_error") is not True
            and isinstance(text, str)
            and bool(text.strip())
        )
        return TurnResult(
            response=text if isinstance(text, str) else "",
            raw_output=response.stdout,
            stderr=response.stderr,
            returncode=response.returncode,
            completed=completed,
            duration_seconds=response.duration_seconds,
            session_id=result_item.get("session_id"),
        )

