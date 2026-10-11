"""Offline regression for the QwenPaw console client; no product or network is used."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from agent_models.interaction import PermissionPolicy
from agent_models.qwenpaw.client import (
    QwenPawClient, TurnTranscript, decide_approval, iter_sse_events,
)

# Shapes copied from a QwenPaw 2.2.1 shell-tool turn (local_docs probe capture t1_tool_shell).
TOOL_TURN = [
    {"object": "response", "status": "created", "sequence_number": 1},
    {"object": "response", "status": "in_progress", "sequence_number": 2},
    {"object": "message", "type": "heartbeat", "sequence_number": 3},
    {"id": "m_r", "object": "message", "type": "reasoning", "status": "in_progress", "sequence_number": 4},
    {"object": "content", "type": "text", "delta": True, "msg_id": "m_r", "text": "think", "sequence_number": 5},
    {"id": "m_r", "object": "message", "type": "reasoning", "status": "completed",
     "content": [{"type": "text", "text": "think"}], "sequence_number": 6},
    {"id": "m_c", "object": "message", "type": "plugin_call", "status": "completed", "sequence_number": 7,
     "content": [{"type": "data", "data": {"call_id": "c1", "name": "execute_shell_command",
                                           "arguments": "{\"command\":\"echo X\"}"}}]},
    {"id": "m_o", "object": "message", "type": "plugin_call_output", "status": "completed", "sequence_number": 8,
     "content": [{"type": "data", "data": {"call_id": "c1", "name": "execute_shell_command",
                                           "output": "X", "state": "success"}}]},
    {"id": "m_a", "object": "message", "type": "message", "status": "in_progress", "sequence_number": 9},
    {"object": "content", "type": "text", "delta": True, "msg_id": "m_a", "text": "输出", "sequence_number": 10},
    {"object": "content", "type": "text", "delta": True, "msg_id": "m_a", "text": "：X", "sequence_number": 11},
    {"object": "response", "status": "completed", "sequence_number": 12},
]


def _sse(events: list[dict[str, Any]]) -> bytes:
    return b"".join(b"data: " + json.dumps(event, ensure_ascii=False).encode() + b"\n\n" for event in events)


def test_sse_parser_handles_multiline_comments_and_done() -> None:
    lines = [b": keepalive\n", b"data: {\"a\":\n", b"data: 1}\n", b"\n", b"data: [DONE]\n", b"\n"]
    assert list(iter_sse_events(lines)) == [{"a": 1}]


def test_sse_parser_rejects_truncated_event() -> None:
    with pytest.raises(ValueError, match="ended inside"):
        list(iter_sse_events([b"data: {}\n"]))


def test_transcript_separates_answer_reasoning_and_tools() -> None:
    transcript = TurnTranscript()
    for event in iter_sse_events(_sse(TOOL_TURN).splitlines(keepends=True)):
        transcript.add(event)
    assert transcript.status == "completed"
    assert transcript.response_text == "输出：X"
    assert transcript.tool_calls == [{"call_id": "c1", "name": "execute_shell_command",
                                      "arguments": "{\"command\":\"echo X\"}", "output": "X", "state": "success"}]
    assert all(not (e.get("object") == "content" and e.get("delta")) for e in transcript.structural_events())


def test_failed_terminal_reports_error_code() -> None:
    transcript = TurnTranscript()
    transcript.add({"object": "response", "status": "failed",
                    "error": {"code": "MODEL_NOT_CONFIGURED", "message": "No active model"}})
    assert transcript.status == "failed"
    assert transcript.error == "MODEL_NOT_CONFIGURED: No active model"


@pytest.mark.parametrize(("item", "policy", "approve", "rule"), [
    ({"tool_name": "Read", "exact_target": "/etc/hosts"}, PermissionPolicy.DENY_UNAPPROVED, True, "read_only"),
    ({"tool_name": "Bash", "exact_target": "ls"}, PermissionPolicy.ALLOW_WORKSPACE_EDITS, False, "not_permitted"),
    ({"tool_name": "Write", "exact_target": "{ws}/a.txt"}, PermissionPolicy.DENY_UNAPPROVED, False, "edit_not_permitted"),
    ({"tool_name": "Write", "exact_target": "{ws}/a.txt"}, PermissionPolicy.ALLOW_WORKSPACE_EDITS, True, "workspace_edit"),
    ({"tool_name": "Edit", "exact_target": "{ws}/../escape.txt"}, PermissionPolicy.ALLOW_WORKSPACE_EDITS,
     False, "edit_outside_workspace"),
    ({"tool_name": "driver:mcp:ats_mock", "tool_source": "mcp:ats_mock"}, PermissionPolicy.DENY_UNAPPROVED,
     True, "evaluator_mock_tool"),
    ({"tool_name": "driver:mcp:other", "tool_source": "mcp:other"}, PermissionPolicy.ALLOW_WORKSPACE_EDITS,
     False, "not_permitted"),
    ({"tool_name": "Bash", "exact_target": "rm -rf x"}, PermissionPolicy.BYPASS, True, "bypass"),
])
def test_unattended_approval_policy(tmp_path: Path, item: dict[str, str], policy: PermissionPolicy,
                                    approve: bool, rule: str) -> None:
    item = {key: value.replace("{ws}", str(tmp_path)) for key, value in item.items()}
    decision = decide_approval(item, policy=policy, allow_tools=True, project_dir=tmp_path, mock_configured=True)
    assert (decision.approve, decision.rule) == (approve, rule)


def test_tools_disabled_and_ask_policy(tmp_path: Path) -> None:
    read = {"tool_name": "Read", "exact_target": "x"}
    assert not decide_approval(read, policy=PermissionPolicy.BYPASS, allow_tools=False,
                               project_dir=tmp_path, mock_configured=False).approve
    with pytest.raises(ValueError, match="interactive"):
        decide_approval(read, policy=PermissionPolicy.ASK, allow_tools=True,
                        project_dir=tmp_path, mock_configured=False)


class _FakeConsole:
    """Loopback stand-in for QwenPaw's chat, approval, chats and stop endpoints."""

    def __init__(self, *, pending: list[dict[str, Any]] | None = None, hang: bool = False) -> None:
        self.pending = list(pending or [])
        self.hang = hang
        self.answers: list[tuple[str, dict[str, Any]]] = []
        self.stopped = threading.Event()
        self.released = threading.Event()
        console = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                pass

            def _json(self, payload: Any) -> None:
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                if self.path.startswith("/api/approval/list"):
                    self._json({"pending_approvals": [p for p in console.pending
                                                      if p["request_id"] not in {a[1]["request_id"] for a in console.answers}]})
                elif self.path == "/api/chats":
                    self._json([{"session_id": "s1", "status": "idle"}])
                else:
                    self._json({})

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/console/chat":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    self.wfile.write(_sse(TOOL_TURN[:2]))
                    self.wfile.flush()
                    if console.hang:
                        console.stopped.wait(10)
                    else:
                        console.released.wait(10)
                    self.wfile.write(_sse(TOOL_TURN[2:]))
                    self.wfile.flush()
                elif self.path.startswith("/api/approval/"):
                    console.answers.append((self.path.rsplit("/", 1)[1], body))
                    console.released.set()
                    self._json({"success": True})
                elif self.path.startswith("/api/console/chat/stop"):
                    console.stopped.set()
                    self._json({"stopped": True})
                else:
                    self._json({})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        if not self.pending:
            self.released.set()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def test_turn_answers_each_pending_approval_once(tmp_path: Path) -> None:
    console = _FakeConsole(pending=[{"request_id": "r1", "session_id": "s1", "tool_name": "Bash",
                                     "exact_target": "ls"}])
    try:
        outcome = QwenPawClient(console.url).run_turn(
            "hi", session_id="s1", user_id="u", timeout=20, poll_interval=0.1,
            decide=lambda item: decide_approval(item, policy=PermissionPolicy.DENY_UNAPPROVED, allow_tools=True,
                                                project_dir=tmp_path, mock_configured=False))
    finally:
        console.close()
    assert outcome.transcript.status == "completed" and not outcome.timed_out
    assert [(kind, body["request_id"]) for kind, body in console.answers] == [("deny", "r1")]
    assert [decision.rule for decision in outcome.decisions] == ["not_permitted"]
    assert outcome.transcript.response_text == "输出：X"


def test_turn_deadline_requests_product_stop() -> None:
    console = _FakeConsole(hang=True)
    try:
        outcome = QwenPawClient(console.url).run_turn(
            "hi", session_id="s1", user_id="u", timeout=1.0, poll_interval=0.1,
            decide=lambda item: pytest.fail("no approvals expected"))
    finally:
        console.close()
    assert outcome.timed_out and outcome.stopped is True
    assert console.stopped.is_set()
