"""Bridge MCP stdio tools to an evaluator-owned loopback runtime.

Protocol: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
Lifecycle: https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
Transport: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
This synchronous bridge exposes only tools and ping; it does not claim streaming,
sampling, notifications, or cancellation of an already executing business call.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import sys
from typing import Any
from urllib.parse import urlsplit

MAX_MESSAGE_BYTES = 1_048_576
SUPPORTED_VERSIONS = ("2025-06-18", "2024-11-05")


class BridgeError(RuntimeError):
    def __init__(self, message: str, *, protocol_code: int = -32603) -> None:
        super().__init__(message)
        self.protocol_code = protocol_code


class HttpBridge:
    """Use only literal loopback HTTP, with no proxy, redirect or DNS fallback."""

    def __init__(self, url: str, *, timeout: float = 12) -> None:
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port is None
                or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment
                or not parsed.path.startswith("/") or parsed.path in {"", "/"}
                or any(c in parsed.path for c in "\r\n")):
            raise ValueError("Receiver URL must identify a literal loopback endpoint")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError("Bridge timeout must be in (0, 300]")
        self.port = parsed.port
        self.path = parsed.path.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.timeout)
        try:
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8") if payload is not None else None
            if body is not None and len(body) > MAX_MESSAGE_BYTES:
                raise BridgeError("Tool request exceeds byte limit", protocol_code=-32602)
            connection.request(method, self.path + route, body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            raw = response.read(MAX_MESSAGE_BYTES + 1)
            if len(raw) > MAX_MESSAGE_BYTES:
                raise BridgeError("Receiver response exceeds byte limit")
            if response.status == 400:
                raise BridgeError("Invalid tool name or arguments", protocol_code=-32602)
            if response.status != 200:
                raise BridgeError("Controlled tool receiver could not complete request")
            value = json.loads(raw, parse_constant=_reject_constant)
            if not isinstance(value, dict):
                raise BridgeError("Invalid receiver response")
            return value
        except (OSError, http.client.HTTPException, ValueError, RecursionError) as exc:
            raise BridgeError("Controlled tool receiver unavailable or invalid") from exc
        finally:
            connection.close()


def _reject_constant(value: str) -> None:
    raise ValueError("Nonfinite JSON is invalid")


def _result(request_id: str | int, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: str | int | None, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def tool_result(body: Any, content_type: str, is_error: bool, *, structured: bool = True) -> dict[str, Any]:
    result = {"content": [{"type": "text", "text": body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)}],
              "isError": is_error}
    if structured and content_type == "application/json" and isinstance(body, dict):
        result["structuredContent"] = body
    return result


class McpSession:
    def __init__(self, bridge: HttpBridge) -> None:
        self.bridge = bridge
        self.version: str | None = None
        self.initialized = False

    def handle(self, request: Any) -> dict[str, Any] | None:
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            return _error(None, -32600, "Invalid JSON-RPC request")
        method = request["method"]
        if "id" not in request:
            if method == "notifications/initialized" and self.version is not None:
                self.initialized = True
            return None
        request_id = request["id"]
        if type(request_id) not in (str, int):
            return _error(None, -32600, "Invalid request identifier")
        params = request.get("params", {})
        if not isinstance(params, dict):
            return _error(request_id, -32602, "Parameters must be an object")
        if method == "initialize":
            if self.version is not None:
                return _error(request_id, -32600, "Already initialized")
            requested = params.get("protocolVersion")
            info = params.get("clientInfo")
            if (not isinstance(requested, str) or not isinstance(params.get("capabilities"), dict)
                    or not isinstance(info, dict) or not isinstance(info.get("name"), str)
                    or not isinstance(info.get("version"), str)):
                return _error(request_id, -32602, "Invalid initialization parameters")
            self.version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            return _result(request_id, {"protocolVersion": self.version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "AgentTestTool Controlled Tools", "version": "2.0"}})
        if method == "ping":
            return _result(request_id, {})
        if not self.initialized:
            return _error(request_id, -32600, "Complete initialization before tool requests")
        try:
            if method == "tools/list":
                if params.get("cursor") is not None:
                    return _error(request_id, -32602, "This tool list has no continuation cursor")
                data = self.bridge.request("GET", "/tools")
                if not isinstance(data.get("tools"), list):
                    raise BridgeError("Invalid receiver tool list")
                return _result(request_id, {"tools": data["tools"]})
            if method == "tools/call":
                if not isinstance(params.get("name"), str) or not isinstance(params.get("arguments", {}), dict):
                    return _error(request_id, -32602, "Invalid tool call parameters")
                data = self.bridge.request("POST", "/call", {"name": params["name"], "arguments": params.get("arguments", {})})
                if "body" not in data or not isinstance(data.get("content_type"), str) or type(data.get("is_error")) is not bool:
                    raise BridgeError("Invalid receiver tool result")
                result = tool_result(data["body"], data["content_type"], data["is_error"], structured=self.version == "2025-06-18")
                # Namespaced result metadata ties the wire response to evaluator events.
                if isinstance(data.get("correlation_id"), str):
                    result["_meta"] = {"agenttesttool/correlation_id": data["correlation_id"]}
                return _result(request_id, result)
            return _error(request_id, -32601, "Method not found")
        except BridgeError as exc:
            return _error(request_id, exc.protocol_code, str(exc))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receiver-url", required=True)
    parser.add_argument("--timeout", type=float, default=12)
    args = parser.parse_args()
    try:
        session = McpSession(HttpBridge(args.receiver_url, timeout=args.timeout))
    except ValueError:
        print("Invalid controlled tool bridge configuration", file=sys.stderr)
        return 2
    while True:
        raw = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1)
        if not raw:
            return 0
        if len(raw) > MAX_MESSAGE_BYTES:
            response = _error(None, -32600, "MCP message exceeds byte limit")
            print(json.dumps(response), flush=True)
            return 2  # Do not consume an attacker-controlled unbounded line.
        try:
            request = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, RecursionError):
            response = _error(None, -32700, "Invalid JSON message")
        else:
            response = session.handle(request)
        if response is not None:
            # Escaping also keeps malformed surrogate identifiers from crashing stdio.
            encoded = json.dumps(response, ensure_ascii=True, allow_nan=False).encode("utf-8")
            sys.stdout.buffer.write(encoded + b"\n")
            sys.stdout.buffer.flush()


if __name__ == "__main__":
    raise SystemExit(main())
