"""Serve one deterministic MCP tool for CodeBuddy security tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--content-type", required=True)
    parser.add_argument("--body-json", required=True)
    parser.add_argument("--log-path", required=True)
    args = parser.parse_args()
    body = json.loads(args.body_json)
    log_path = Path(args.log_path)

    for line in sys.stdin:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(request, dict):
            continue
        response, log_record = _handle(request, args.tool_name, args.content_type, body)
        if log_record is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(log_record, ensure_ascii=False) + "\n")
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def _handle(
    request: dict[str, Any],
    tool_name: str,
    content_type: str,
    body: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    request_id = request.get("id")
    method = request.get("method")
    if request_id is None:
        return None, None
    if method == "initialize":
        requested_version = request.get("params", {}).get("protocolVersion", "2024-11-05")
        return (
            _result(
                request_id,
                {
                    "protocolVersion": requested_version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "AgentTestTool Mock Tool", "version": "1.0"},
                },
            ),
            None,
        )
    if method == "ping":
        return _result(request_id, {}), None
    if method == "tools/list":
        return (
            _result(
                request_id,
                {
                    "tools": [
                        {
                            "name": tool_name,
                            "description": "Return a deterministic empty lookup result.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                },
                                "additionalProperties": True,
                            },
                        }
                    ]
                },
            ),
            None,
        )
    if method == "tools/call":
        params = request.get("params")
        name = params.get("name") if isinstance(params, dict) else None
        arguments = params.get("arguments", {}) if isinstance(params, dict) else {}
        if name != tool_name:
            return _error(request_id, -32602, f"Unknown tool: {name}"), None
        text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
        tool_result: dict[str, Any] = {
            "content": [{"type": "text", "text": text}],
            "isError": False,
        }
        if content_type == "application/json" and isinstance(body, dict):
            tool_result["structuredContent"] = body
        log_record = {
            "tool_name": tool_name,
            "arguments": arguments,
            "content_type": content_type,
            "body": body,
            "result": tool_result,
        }
        return _result(request_id, tool_result), log_record
    return _error(request_id, -32601, f"Method not found: {method}"), None


def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


if __name__ == "__main__":
    raise SystemExit(main())
