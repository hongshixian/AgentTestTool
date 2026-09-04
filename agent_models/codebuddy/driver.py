"""CodeBuddy commands and JSON output normalization."""

from __future__ import annotations

import json
from typing import Any

from agent_models.result import TurnResult
from agent_models.codebuddy.transport import StdioResponse


class CodeBuddyDriver:
    AUTHENTICATION_PROBE = "这是自动化认证状态检查。请只回复 AUTH_OK。"

    def parse_turn(self, response: StdioResponse) -> TurnResult:
        items = _parse_output_items(response.stdout)
        result_item = next(
            (
                item
                for item in reversed(items)
                if isinstance(item, dict) and item.get("type") == "result"
            ),
            None,
        )

        if result_item is None:
            assistant_item, assistant_text = _last_assistant_text(items)
            completed = response.returncode == 0 and bool(assistant_text.strip())
            return TurnResult(
                response=assistant_text,
                raw_output=response.stdout,
                stderr=response.stderr,
                returncode=response.returncode,
                completed=completed,
                duration_seconds=response.duration_seconds,
                session_id=_session_id(assistant_item),
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


def _parse_output_items(raw_output: str) -> list[Any]:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return _parse_complete_array_items(raw_output)
    return payload if isinstance(payload, list) else [payload]


def _parse_complete_array_items(raw_output: str) -> list[Any]:
    stripped = raw_output.lstrip()
    if not stripped.startswith("["):
        return []

    decoder = json.JSONDecoder()
    index = raw_output.index("[") + 1
    items: list[Any] = []
    while index < len(raw_output):
        while index < len(raw_output) and raw_output[index] in " \t\r\n,":
            index += 1
        if index >= len(raw_output) or raw_output[index] == "]":
            break
        try:
            item, index = decoder.raw_decode(raw_output, index)
        except json.JSONDecodeError:
            break
        items.append(item)
    return items


def _last_assistant_text(items: list[Any]) -> tuple[dict[str, Any] | None, str]:
    for item in reversed(items):
        if not isinstance(item, dict) or item.get("type") != "assistant":
            continue
        message = item.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        texts = [
            part.get("text")
            for part in content
            if isinstance(part, dict)
            and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        ]
        if texts:
            return item, "\n".join(texts)
    return None, ""


def _session_id(item: dict[str, Any] | None) -> str | None:
    if item is None:
        return None
    value = item.get("session_id") or item.get("sessionId")
    return value if isinstance(value, str) else None
