"""Exercise the OpenCode HTTP/SSE adapter without a model provider."""

from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import psutil

from agent_models.interaction import AgentEventType, PermissionDecision, PermissionPolicy
from agent_models.opencode import interactive
from agent_models.opencode.interactive import OpenCodeInteractiveSession


class _FakeProcess:
    def __init__(self) -> None:
        self.pid = 2000000000
        self.stopped = False
        self.group_signals: list[int] = []

    def poll(self) -> int | None:
        return 0 if self.stopped else None

    def terminate(self) -> None:
        self.stopped = True

    def wait(self, *, timeout: int) -> int:
        return 0

    def kill(self) -> None:
        self.stopped = True


class _OpenCodeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.streams: list[queue.Queue[object]] = []
        self.messages: list[dict[str, object]] = []
        self.permission_rules: list[dict[str, str]] = []
        self.responses: list[str] = []
        self.sessions = 0
        self.inputs: list[dict[str, object]] = []
        self.lock = threading.RLock()

    def publish(self, kind: str, props: dict[str, object]) -> None:
        with self.lock:
            for output in self.streams:
                output.put({"type": kind, "properties": {"sessionID": "ses_test", **props}})

    def finish(self, prompt: str) -> None:
        with self.lock:
            self.messages.append({"info": {"id": f"msg_assistant_{len(self.messages)}", "role": "assistant"}, "parts": [{"type": "text", "text": "reply:" + prompt}]})
        self.publish("message.part.delta", {"field": "text", "delta": "reply:" + prompt})
        self.publish("session.idle", {})


class _Handler(BaseHTTPRequestHandler):
    server: _OpenCodeServer

    def log_message(self, *_args: object) -> None:
        pass

    def _json(self, status: int, payload: object) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/session/status":
            self._json(200, {})
        elif path == "/session/ses_test/message":
            with self.server.lock:
                self._json(200, list(self.server.messages))
        elif path == "/event":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            outgoing: queue.Queue[object] = queue.Queue()
            with self.server.lock:
                self.server.streams.append(outgoing)
            try:
                while True:
                    try:
                        item = outgoing.get(timeout=0.2)
                    except queue.Empty:
                        if self.server._BaseServer__is_shut_down.is_set():
                            break
                        continue
                    self.wfile.write(b"data: " + json.dumps(item).encode() + b"\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self._json(404, {})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length)) if length else {}
        if path == "/session":
            with self.server.lock:
                self.server.sessions += 1
                self.server.permission_rules = payload["permission"]
            self._json(200, {"id": "ses_test"})
        elif path == "/session/ses_test/prompt_async":
            self.server.inputs.append(payload)
            prompt = payload["parts"][0]["text"]
            self.server.messages.append({"info": {"id": payload["messageID"], "role": "user"}, "parts": []})
            self.server.publish("session.status", {"status": {"type": "busy"}})
            if prompt == "ASK":
                self.server.publish("permission.asked", {"id": "per_1", "permission": "bash", "patterns": ["*"]})
            elif prompt != "WAIT":
                self.server.finish(prompt)
            self._json(204, {})
        elif path == "/permission/per_1/reply":
            self.server.responses.append(payload["reply"])
            self.server.finish("permission:" + payload["reply"])
            self._json(200, True)
        elif path == "/session/ses_test/abort":
            self.server.publish("session.idle", {})
            self._json(200, True)
        elif path == "/api/session/ses_test/permission/per_1/reply":
            self.server.responses.append(payload["reply"])
            self.server.finish("permission:" + payload["reply"])
            self._json(200, True)
        else:
            self._json(404, {})


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch):
    server = _OpenCodeServer()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    created: list[tuple[tuple[str, ...], dict[str, str], _FakeProcess]] = []

    def fake_popen(command, *, env, **_kwargs):
        process = _FakeProcess()
        created.append((tuple(command), env, process))
        return process

    def fake_killpg(group_id: int, signal_number: int) -> None:
        assert group_id == 2000000000
        assert signal_number in {signal.SIGTERM, signal.SIGKILL}
        for _, _, process in created:
            process.group_signals.append(signal_number)
            process.stopped = True

    monkeypatch.setattr(interactive, "_unused_loopback_port", lambda: server.server_port)
    monkeypatch.setattr(interactive.subprocess, "Popen", fake_popen)
    if os.name != "nt":
        monkeypatch.setattr(interactive.os, "killpg", fake_killpg)
    yield server, created
    server.shutdown()
    server.server_close()
    server_thread.join(timeout=3)


def _session(tmp_path: Path, *, policy: PermissionPolicy = PermissionPolicy.ASK) -> OpenCodeInteractiveSession:
    return OpenCodeInteractiveSession(
        workspace=tmp_path,
        environment={},
        model="iiis/infi/deepseek-v4.1-flash",
        timeout=2,
        permission_policy=policy,
    )


def test_multiturn_reuses_server_and_correlates_messages(tmp_path: Path, fake_server) -> None:
    server, created = fake_server
    with _session(tmp_path) as session:
        first = session.send_input("first")
        first_result = session.wait_for_completion(first)
        second = session.send_input("second")
        second_result = session.wait_for_completion(second)
        assert first_result.completed and second_result.completed
        assert first_result.response == "reply:first"
        assert second_result.response == "reply:second"
        assert first_result.session_id == second_result.session_id == "ses_test"
        assert server.sessions == 1
        assert created[0][0][1:3] == ("serve", "--pure")
        assert created[0][1]["XDG_CONFIG_HOME"] != str(Path.home() / ".config")
        assert created[0][1]["OPENCODE_SERVER_PASSWORD"]
    assert created[0][2].stopped
    if os.name != "nt":
        assert created[0][2].group_signals == [signal.SIGTERM]


@pytest.mark.parametrize("policy,expected", [
    (PermissionPolicy.ASK, "ask"),
    (PermissionPolicy.DENY_UNAPPROVED, "ask"),
    (PermissionPolicy.BYPASS, "allow"),
])
def test_native_permission_rules(tmp_path: Path, fake_server, policy, expected) -> None:
    server, _ = fake_server
    with _session(tmp_path, policy=policy):
        assert server.permission_rules[0] == {"permission": "*", "pattern": "*", "action": expected}


def test_explicit_permission_reply_never_always_allows(tmp_path: Path, fake_server) -> None:
    server, _ = fake_server
    with _session(tmp_path) as session:
        turn = session.send_input("ASK")
        event = session.wait_for_event(AgentEventType.PERMISSION_REQUEST, timeout=2, after_sequence=turn.after_sequence)
        assert event.request_id == "per_1"
        session.respond_to_confirmation(event, PermissionDecision.ALLOW, reason="fixture tool")
        assert session.wait_for_completion(turn).response == "reply:permission:once"
        assert server.responses == ["once"]
        with pytest.raises(ValueError, match="already been answered"):
            session.respond_to_confirmation(event, PermissionDecision.ALLOW, reason="duplicate")


def test_unattended_policy_auto_rejects_request(tmp_path: Path, fake_server) -> None:
    server, _ = fake_server
    with _session(tmp_path, policy=PermissionPolicy.DENY_UNAPPROVED) as session:
        turn = session.send_input("ASK")
        assert session.wait_for_completion(turn).completed
        assert server.responses == ["reject"]


def test_abort_ack_and_terminal_result_is_not_success(tmp_path: Path, fake_server) -> None:
    with _session(tmp_path) as session:
        turn = session.send_input("WAIT")
        assert session.interrupt_task(reason="test cancellation").success
        result = session.wait_for_completion(turn)
        assert not result.completed
        assert "cancelled" in result.stderr
        assert not session.interrupt_task(reason="already finished").success


def test_foreign_session_events_do_not_complete_turn(tmp_path: Path, fake_server) -> None:
    server, _ = fake_server
    with _session(tmp_path) as session:
        turn = session.send_input("WAIT")
        server.publish("session.idle", {"sessionID": "ses_other"})
        with pytest.raises(TimeoutError, match="timed out"):
            session.wait_for_completion(turn, timeout=0.1)
        assert session.interrupt_task(reason="cleanup").success
        assert not session.wait_for_completion(turn).completed


def test_unexpected_event_stream_disconnect_fails_closed(tmp_path: Path, fake_server) -> None:
    with _session(tmp_path) as session:
        turn = session.send_input("WAIT")
        session._collector_error = "offline disconnect"
        with pytest.raises(RuntimeError, match="event collection failed"):
            session.wait_for_completion(turn, timeout=0.1)


def test_mcp_config_merges_isolated_config(tmp_path: Path, fake_server) -> None:
    _, created = fake_server
    with OpenCodeInteractiveSession(
        workspace=tmp_path,
        environment={"OPENCODE_CONFIG_CONTENT": '{"model":"iiis/infi/deepseek-v4.1-flash"}'},
        model="iiis/infi/deepseek-v4.1-flash",
        timeout=2,
        permission_policy=PermissionPolicy.ASK,
        mcp_config={"fixture": {"type": "local", "command": ["python", "tool.py"]}},
    ):
        config = json.loads(created[0][1]["OPENCODE_CONFIG_CONTENT"])
        assert config["model"] == "iiis/infi/deepseek-v4.1-flash"
        assert "fixture" in config["mcp"]


def test_no_tools_overrides_bypass_and_configured_mcp(tmp_path: Path, fake_server) -> None:
    server, created = fake_server
    with OpenCodeInteractiveSession(
        workspace=tmp_path,
        environment={"OPENCODE_CONFIG_CONTENT": '{"model":"iiis/model","tools":{"bash":true}}'},
        model="iiis/infi/deepseek-v4.1-flash",
        timeout=2,
        permission_policy=PermissionPolicy.BYPASS,
        allow_tools=False,
        mcp_config={"fixture": {"type": "local", "command": ["python", "tool.py"]}},
    ):
        config = json.loads(created[0][1]["OPENCODE_CONFIG_CONTENT"])
        assert config["tools"] == {"*": False, "bash": False}
        assert config["mcp"] == {}
        assert server.permission_rules == [{"permission": "*", "pattern": "*", "action": "deny"}]


def test_no_tools_disables_named_tools_from_saved_profile(tmp_path: Path, fake_server) -> None:
    _, created = fake_server
    config_dir = tmp_path / "opencode-config"
    config_dir.mkdir()
    (config_dir / "opencode.json").write_text(
        '{"tools":{"ats_mock_receive":true,"bash":true}}', encoding="utf-8"
    )
    with OpenCodeInteractiveSession(
        workspace=tmp_path,
        environment={"OPENCODE_CONFIG_DIR": str(config_dir)},
        model="iiis/infi/deepseek-v4.1-flash",
        timeout=2,
        permission_policy=PermissionPolicy.BYPASS,
        allow_tools=False,
    ):
        config = json.loads(created[0][1]["OPENCODE_CONFIG_CONTENT"])
        assert config["tools"] == {"*": False, "bash": False, "ats_mock_receive": False}
        assert config["mcp"] == {}


def test_v2_permission_uses_matching_reply_endpoint(tmp_path: Path, fake_server) -> None:
    server, _ = fake_server
    with _session(tmp_path) as session:
        turn = session.send_input("WAIT")
        server.publish(
            "permission.v2.asked",
            {"id": "per_1", "action": "bash", "resources": ["*"]},
        )
        request = session.wait_for_event(AgentEventType.PERMISSION_REQUEST, timeout=2, after_sequence=turn.after_sequence)
        session.respond_to_confirmation(request, PermissionDecision.DENY, reason="untrusted command")
        assert server.responses == ["reject"]
        assert session.wait_for_completion(turn).response == "reply:permission:reject"


def test_close_callback_is_called_once(tmp_path: Path, fake_server) -> None:
    released: list[str] = []
    session = OpenCodeInteractiveSession(
        workspace=tmp_path,
        environment={},
        model="iiis/infi/deepseek-v4.1-flash",
        timeout=2,
        permission_policy=PermissionPolicy.ASK,
        close_callback=lambda: released.append("released"),
    )
    session.close()
    session.close()
    assert released == ["released"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group cleanup regression")
def test_close_still_signals_process_group_if_server_parent_already_exited(
    tmp_path: Path, fake_server,
) -> None:
    _, created = fake_server
    session = _session(tmp_path)
    created[0][2].stopped = True
    session.close()
    assert created[0][2].group_signals == [signal.SIGTERM]


def test_close_does_not_release_lease_until_process_cleanup_succeeds(
    tmp_path: Path, fake_server, monkeypatch: pytest.MonkeyPatch,
) -> None:
    released: list[str] = []
    session = OpenCodeInteractiveSession(
        workspace=tmp_path,
        environment={},
        model="iiis/infi/deepseek-v4.1-flash",
        timeout=2,
        permission_policy=PermissionPolicy.ASK,
        close_callback=lambda: released.append("released"),
    )
    def fail_stop(_process: object) -> None:
        raise interactive.ProcessCleanupError("cleanup unconfirmed")

    with monkeypatch.context() as patcher:
        patcher.setattr(interactive, "_stop_posix_server", fail_stop)
        with pytest.raises(interactive.ProcessCleanupError, match="unconfirmed"):
            session.close()
    assert released == []
    session.close()
    session.close()
    assert released == ["released"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group cleanup regression")
def test_process_cleanup_kills_child_after_server_exits() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", (
            "import subprocess,sys; "
            "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); "
            "print(p.pid,flush=True)"
        )],
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    assert process.stdout is not None
    child_pid = int(process.stdout.readline())
    try:
        assert process.wait(timeout=3) == 0
        interactive._stop_posix_server(process)
        try:
            assert psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if psutil.pid_exists(child_pid):
            child = psutil.Process(child_pid)
            if child.status() != psutil.STATUS_ZOMBIE:
                child.kill()
        process.wait(timeout=3)


def test_invalid_steering_cannot_be_reported_as_success(tmp_path: Path, fake_server) -> None:
    with _session(tmp_path) as session:
        assert not session.steer("change answer").success
