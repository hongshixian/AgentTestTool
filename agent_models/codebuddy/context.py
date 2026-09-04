"""Map product-neutral request context to CodeBuddy CLI headers."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping

from agent_models.evidence import RequestContext


_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_REQUIRED_KEYS = ("user_id", "instance_id", "run_id")


class CodeBuddyRequestContextAdapter:
    def __init__(self, headers: Mapping[str, str] | None = None) -> None:
        self.headers = dict(headers or {})

    @classmethod
    def from_environment(cls) -> CodeBuddyRequestContextAdapter:
        raw = os.environ.get("CODEBUDDY_REQUEST_CONTEXT_HEADERS", "").strip()
        if not raw:
            return cls()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("CODEBUDDY_REQUEST_CONTEXT_HEADERS 必须是 JSON 对象") from error
        if not isinstance(parsed, dict):
            raise ValueError("CODEBUDDY_REQUEST_CONTEXT_HEADERS 必须是 JSON 对象")
        headers: dict[str, str] = {}
        for key in _REQUIRED_KEYS:
            value = parsed.get(key)
            if not isinstance(value, str) or not _HEADER_NAME.fullmatch(value):
                raise ValueError(
                    f"CODEBUDDY_REQUEST_CONTEXT_HEADERS.{key} 必须是有效 HTTP Header 名"
                )
            headers[key] = value
        return cls(headers)

    def is_available(self) -> bool:
        return all(key in self.headers for key in _REQUIRED_KEYS)

    def extra_args(self, context: RequestContext | None) -> tuple[str, ...]:
        if context is None:
            return ()
        if not self.is_available():
            raise RuntimeError("CodeBuddy 请求上下文 Header 映射未配置")
        values: list[tuple[str, str]] = [
            (self.headers["user_id"], context.user_id),
            (self.headers["run_id"], context.run_id),
        ]
        if context.instance_id is not None:
            values.append((self.headers["instance_id"], context.instance_id))
        for _, value in values:
            if "\r" in value or "\n" in value:
                raise ValueError("请求上下文值不得包含换行符")
        return ("--header", *(f"{name}: {value}" for name, value in values))
