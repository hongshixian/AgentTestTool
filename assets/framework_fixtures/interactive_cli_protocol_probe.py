"""Emit deterministic CodeBuddy-like stream-json events for offline tests."""

from __future__ import annotations

import json
import sys


SESSION_ID = "offline-session"
initialized = False
turn_number = 0
pending_permission: str | None = None
pending_turn = False


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def result(text: str, *, success: bool = True) -> None:
    if success:
        emit(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": text,
                "session_id": SESSION_ID,
                "duration_ms": 25,
                "num_turns": 1,
                "permission_denials": [],
            }
        )
    else:
        emit(
            {
                "type": "result",
                "subtype": "error_during_execution",
                "is_error": True,
                "session_id": SESSION_ID,
                "duration_ms": 25,
                "num_turns": 1,
                "permission_denials": [],
                "errors": [text],
            }
        )


for line in sys.stdin:
    message = json.loads(line)
    message_type = message.get("type")
    if message_type == "control_request":
        request_id = message["request_id"]
        request = message["request"]
        subtype = request["subtype"]
        if subtype == "initialize":
            emit(
                {
                    "type": "control_response",
                    "response": {
                        "subtype": "success",
                        "request_id": request_id,
                        "response": {
                            "currentModelId": "offline-model",
                            "account": {
                                "token": "fixture-secret-token",
                                "userName": "fixture-user",
                            },
                        },
                    },
                }
            )
        elif subtype == "steer":
            emit(
                {
                    "type": "control_response",
                    "response": {
                        "subtype": "success",
                        "request_id": request_id,
                        "response": {
                            "session_id": SESSION_ID,
                            "steered": pending_turn,
                            **({} if pending_turn else {"reason": "idle"}),
                        },
                    },
                }
            )
            if pending_turn:
                pending_turn = False
                text = request["content_blocks"][0]["text"]
                result(f"steered:{text}")
        elif subtype == "interrupt":
            emit(
                {
                    "type": "control_response",
                    "response": {
                        "subtype": "success",
                        "request_id": request_id,
                        "response": {
                            "session_id": SESSION_ID,
                            "interrupted": pending_turn,
                            "reason": (
                                request.get("reason", "") if pending_turn else "idle"
                            ),
                        },
                    },
                }
            )
            if pending_turn:
                pending_turn = False
                result("interrupted", success=False)
        continue

    if message_type == "control_response":
        response = message["response"]
        if response["request_id"] == pending_permission:
            decision = response["response"]
            label = (
                "allow"
                if decision["allowed"]
                else "cancel"
                if decision.get("interrupt")
                else "deny"
            )
            emit(
                {
                    "type": "user",
                    "session_id": SESSION_ID,
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "tool-1",
                                "content": label,
                                "is_error": not decision["allowed"],
                            }
                        ]
                    },
                }
            )
            result(f"permission:{label}")
            pending_permission = None
        continue

    if message_type != "user":
        continue

    if not initialized:
        initialized = True
        emit(
            {
                "type": "system",
                "subtype": "init",
                "session_id": SESSION_ID,
                "cwd": "/fixture",
                "tools": ["Read", "Write"],
                "mcp_servers": [],
                "model": "offline-model",
                "permissionMode": "default",
                "output_style": "default",
            }
        )
    turn_number += 1
    prompt = message["message"]["content"][0]["text"]
    if prompt == "MALFORMED":
        print("{not-json", flush=True)
        continue
    if prompt == "EXIT":
        raise SystemExit(7)
    if prompt == "WAIT":
        pending_turn = True
        emit(
            {
                "type": "assistant",
                "session_id": SESSION_ID,
                "message": {"content": [{"type": "text", "text": "working"}]},
            }
        )
        continue
    if prompt == "NEED_PERMISSION":
        pending_permission = f"perm-{turn_number}"
        emit(
            {
                "type": "assistant",
                "session_id": SESSION_ID,
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Write",
                            "input": {"file_path": "result.txt", "content": "ok"},
                        }
                    ]
                },
            }
        )
        emit(
            {
                "type": "control_request",
                "request_id": pending_permission,
                "request": {
                    "subtype": "can_use_tool",
                    "tool_name": "Write",
                    "input": {"file_path": "result.txt", "content": "ok"},
                    "tool_use_id": "tool-1",
                    "decision_reason": "fixture approval",
                },
            }
        )
        continue
    if prompt == "BACKGROUND":
        emit(
            {
                "type": "system",
                "subtype": "task_started",
                "session_id": SESSION_ID,
                "task_id": "task-1",
                "tool_use_id": "tool-bg",
            }
        )
        emit(
            {
                "type": "system",
                "subtype": "task_updated",
                "session_id": SESSION_ID,
                "task_id": "task-1",
                "patch": {"status": "completed"},
            }
        )
    if prompt == "PARTIAL":
        emit(
            {
                "type": "stream_event",
                "session_id": SESSION_ID,
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "partial-text"},
                },
            }
        )
    if prompt == "STDERR":
        print("fixture diagnostic", file=sys.stderr, flush=True)
    emit(
        {
            "type": "assistant",
            "session_id": SESSION_ID,
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "fixture reasoning"},
                    {"type": "text", "text": f"reply:{prompt}"},
                ]
            },
        }
    )
    result(f"reply:{prompt}")
