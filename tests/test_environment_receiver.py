"""Verify bounded loopback collection independently from any Agent service."""

import http.client
import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from agent_models.environment.receiver import HttpToolReceiver


class Backend:
    def __init__(self):
        self.calls = []
        self.closed = False

    def list_tools(self):
        return [{"name": "lookup", "description": "Lookup", "inputSchema": {"type": "object"}}]

    def call(self, name, arguments, *, correlation_id, timeout):
        if name != "lookup":
            raise ValueError("unknown")
        self.calls.append((name, arguments, correlation_id))
        return SimpleNamespace(body={"value": arguments.get("query")},
                               content_type="application/json", is_error=False)

    def close(self):
        self.closed = True


def request(receiver, method, route, body=None, headers=None):
    url = urlsplit(receiver.url)
    conn = http.client.HTTPConnection(url.hostname, url.port, timeout=2)
    try:
        conn.request(method, url.path + route, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


def test_real_socket_receives_request_and_preserves_correlation():
    backend = Backend()
    events = []
    with HttpToolReceiver(backend, event_sink=lambda *a, **k: events.append((a, k))) as receiver:
        assert receiver.health()["healthy"]
        assert request(receiver, "GET", "/tools")[1]["tools"][0]["name"] == "lookup"
        status, result = request(receiver, "POST", "/call", json.dumps({"name": "lookup", "arguments": {"query": "canary"}}))
        assert status == 200 and result["body"] == {"value": "canary"}
        assert result["correlation_id"] == backend.calls[0][2]
        assert [x[0][1] for x in events].count("http_received") == 2
    assert backend.closed and not receiver.health()["healthy"]


@pytest.mark.parametrize("headers", [{"Host": "attacker.invalid"}, {"Origin": "https://attacker.invalid"}])
def test_rejects_cross_origin_and_dns_rebinding(headers):
    with HttpToolReceiver(Backend()) as receiver:
        assert request(receiver, "GET", "/tools", headers=headers)[0] == 403


def test_limits_and_invalid_payload_do_not_reach_tool():
    backend = Backend()
    with HttpToolReceiver(backend, max_body_bytes=128) as receiver:
        assert request(receiver, "POST", "/call", "x" * 129)[0] == 413
        assert request(receiver, "POST", "/call", "not-json")[0] == 400
        assert request(receiver, "POST", "/call", '{"name":"lookup","arguments":[]}')[0] == 400
        assert backend.calls == []


def test_recording_failure_is_not_silent_success():
    def fail(*args, **kwargs):
        raise OSError("test failure")
    with pytest.raises(OSError):
        HttpToolReceiver(Backend(), event_sink=fail)


@pytest.mark.parametrize("option,value", [
    ("request_timeout", True), ("request_timeout", "1"),
    ("request_timeout", float("nan")), ("request_timeout", float("inf")),
    ("request_timeout", 0), ("request_timeout", 10 ** 1000),
    ("max_body_bytes", True), ("max_body_bytes", 1.5), ("max_body_bytes", "2"),
    ("max_connections", False), ("max_connections", 2.5), ("max_connections", 0),
])
def test_limits_reject_invalid_types_and_values(option, value):
    with pytest.raises(ValueError):
        HttpToolReceiver(Backend(), **{option: value})


class GatedBackend(Backend):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def call(self, name, arguments, *, correlation_id, timeout):
        self.entered.set()
        if not self.release.wait(timeout):
            raise TimeoutError("test gate timeout")
        return super().call(name, arguments, correlation_id=correlation_id, timeout=timeout)

    def close(self):
        super().close()
        self.release.set()


def test_close_releases_gate_and_waits_for_handler():
    backend = GatedBackend()
    receiver = HttpToolReceiver(backend, request_timeout=1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        response = pool.submit(request, receiver, "POST", "/call", '{"name":"lookup"}')
        assert backend.entered.wait(1)
        receiver.close()
        try:
            response.result(timeout=1)
        except (OSError, http.client.HTTPException):
            pass  # Closing an in-flight connection is deliberate shutdown behavior.
    assert backend.closed and backend.release.is_set()
    assert receiver.health()["active_connections"] == 0
    assert receiver.health()["active_operations"] == 0
    assert not receiver._handlers
    receiver.close()


def _wait_connections(receiver, expected):
    deadline = time.monotonic() + 1
    with receiver._condition:
        while len(receiver._connections) != expected:
            remaining = deadline - time.monotonic()
            assert remaining > 0, "receiver connection registration did not complete"
            receiver._condition.wait(min(remaining, 0.02))


def test_close_stops_slow_headers_without_waiting_for_socket_timeout():
    receiver = HttpToolReceiver(Backend(), request_timeout=2)
    conn = socket.create_connection(("127.0.0.1", receiver._server.server_port), timeout=1)
    try:
        conn.sendall(b"GET / HTTP/1.1\r\nHost:")
        _wait_connections(receiver, 1)
        start = time.monotonic()
        receiver.close()
        assert time.monotonic() - start < 1
        assert conn.recv(1) == b""
        assert receiver.health()["active_connections"] == 0
    finally:
        conn.close()
        receiver.close()


def test_close_failure_is_explicit_and_listener_still_stops():
    class FailedClose(Backend):
        def close(self):
            raise OSError("test cleanup failure")

    receiver = HttpToolReceiver(FailedClose(), request_timeout=0.5)
    with pytest.raises(RuntimeError, match="runtime close failed"):
        receiver.close()
    assert not receiver._thread.is_alive()
    assert receiver.health()["closed"]


def test_close_timeout_can_be_rechecked_after_backend_finishes():
    release = threading.Event()

    class SlowClose(Backend):
        def close(self):
            release.wait(2)

    receiver = HttpToolReceiver(SlowClose(), request_timeout=0.2)
    try:
        start = time.monotonic()
        with pytest.raises(RuntimeError, match="before timeout"):
            receiver.close()
        assert time.monotonic() - start < 1
        assert not receiver._thread.is_alive()
    finally:
        release.set()
        receiver.close()


def test_close_reports_an_uncooperative_handler_then_rechecks():
    class StubbornBackend(GatedBackend):
        def call(self, name, arguments, *, correlation_id, timeout):
            self.entered.set()
            assert self.release.wait(3)
            return Backend.call(self, name, arguments, correlation_id=correlation_id, timeout=timeout)

        def close(self):
            self.closed = True

    backend = StubbornBackend()
    receiver = HttpToolReceiver(backend, request_timeout=0.2)
    with ThreadPoolExecutor(max_workers=1) as pool:
        response = pool.submit(request, receiver, "POST", "/call", '{"name":"lookup"}')
        try:
            assert backend.entered.wait(1)
            with pytest.raises(RuntimeError, match="before timeout"):
                receiver.close()
            assert receiver.health()["active_operations"] == 1
        finally:
            backend.release.set()
            receiver.close()
        with pytest.raises((OSError, http.client.HTTPException)):
            response.result(timeout=1)
    assert receiver.health()["active_operations"] == 0


def test_concurrent_requests_have_distinct_correlations():
    backend = Backend()
    with HttpToolReceiver(backend) as receiver, ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(request, receiver, "POST", "/call",
                               json.dumps({"name": "lookup", "arguments": {"query": index}}))
                   for index in range(16)]
        results = [future.result(timeout=3) for future in futures]
        assert all(status == 200 for status, _ in results)
        assert len({result["correlation_id"] for _, result in results}) == 16
        assert {result["body"]["value"] for _, result in results} == set(range(16))
    assert len(backend.calls) == 16


def test_runtime_timeout_is_recorded_and_returns_504():
    events = []
    with HttpToolReceiver(GatedBackend(), request_timeout=0.15,
                          event_sink=lambda *a, **k: events.append((a, k))) as receiver:
        assert request(receiver, "POST", "/call", '{"name":"lookup"}')[0] == 504
        assert any(event[0][1] == "http_timeout" for event in events)


def _raw_request(receiver, suffix):
    with socket.create_connection(("127.0.0.1", receiver._server.server_port), timeout=1) as conn:
        conn.sendall((f"POST {urlsplit(receiver.url).path}/call HTTP/1.0\r\n"
                      f"Host: {receiver.authority}\r\n" + suffix).encode())
        response = http.client.HTTPResponse(conn)
        response.begin()
        return response.status, response.read()


@pytest.mark.parametrize("headers", [
    "Content-Length: 0\r\nContent-Length: 0\r\n\r\n",
    "Transfer-Encoding: chunked\r\n\r\n",
    "Content-Length: +1\r\n\r\nx",
    "Content-Length: -1\r\n\r\n",
])
def test_invalid_raw_framing_is_rejected_without_tool_execution(headers):
    backend = Backend()
    with HttpToolReceiver(backend) as receiver:
        assert _raw_request(receiver, headers)[0] == 400
    assert backend.calls == []


def test_slow_body_timeout_is_observable():
    events = []
    with HttpToolReceiver(Backend(), request_timeout=0.15,
                          event_sink=lambda *a, **k: events.append((a, k))) as receiver:
        status, _ = _raw_request(receiver, "Content-Length: 100\r\n\r\n{")
        assert status == 504
        assert any(event[0][1] == "http_timeout" for event in events)


def test_slow_header_timeout_is_observable_and_releases_connection():
    rejected = threading.Event()

    def sink(_source, kind, _data, **_kwargs):
        if kind == "http_protocol_rejected":
            rejected.set()

    with HttpToolReceiver(Backend(), request_timeout=0.15, event_sink=sink) as receiver:
        with socket.create_connection(("127.0.0.1", receiver._server.server_port), timeout=1) as conn:
            conn.sendall(b"GET / HTTP/1.1\r\nHost:")
            assert rejected.wait(1)
            assert conn.recv(1) == b""
        _wait_connections(receiver, 0)


def test_evidence_failure_during_request_prevents_tool_execution():
    backend = Backend()

    def sink(_source, kind, _data, **_kwargs):
        if kind == "http_received":
            raise OSError("test collection failure")

    with HttpToolReceiver(backend, event_sink=sink) as receiver:
        with pytest.raises(http.client.HTTPException):
            request(receiver, "POST", "/call", '{"name":"lookup"}')
        assert not receiver.health()["healthy"]
        assert "evidence recording failed" in receiver.health()["errors"]
    assert backend.calls == []


def test_recording_failure_after_response_invalidates_health():
    failed = threading.Event()

    def sink(_source, kind, _data, **_kwargs):
        if kind == "http_responded":
            failed.set()
            raise OSError("test response recording failure")

    with HttpToolReceiver(Backend(), event_sink=sink) as receiver:
        assert request(receiver, "POST", "/call", '{"name":"lookup"}')[0] == 200
        assert failed.wait(1)
        _wait_connections(receiver, 0)
        assert not receiver.health()["healthy"]
        assert "evidence recording failed" in receiver.health()["errors"]


def test_paused_rejects_operations_but_not_health_and_resumes():
    backend = Backend()
    with HttpToolReceiver(backend) as receiver:
        with receiver.paused():
            assert receiver.health()["paused"]
            receiver.probe()
            assert request(receiver, "POST", "/call", '{"name":"lookup"}')[0] == 503
            assert request(receiver, "GET", "/tools")[0] == 503
            assert backend.calls == []
            with receiver.paused():
                assert receiver.health()["paused"]
            assert receiver.health()["paused"]
        assert not receiver.health()["paused"]
        assert request(receiver, "POST", "/call", '{"name":"lookup"}')[0] == 200


def test_pause_waits_until_admitted_operation_finishes():
    backend = GatedBackend()
    with HttpToolReceiver(backend, request_timeout=1) as receiver, ThreadPoolExecutor(max_workers=2) as pool:
        result = pool.submit(request, receiver, "POST", "/call", '{"name":"lookup"}')
        assert backend.entered.wait(1)
        paused = threading.Event()

        def pause():
            with receiver.paused():
                assert receiver.health()["active_operations"] == 0
                paused.set()

        future = pool.submit(pause)
        with receiver._condition:
            receiver._condition.wait_for(lambda: receiver._pause_depth > 0, timeout=0.2)
        assert receiver.health()["paused"]
        assert not paused.is_set()
        backend.release.set()
        assert result.result(timeout=1)[0] == 200
        future.result(timeout=1)
        assert paused.is_set()


def test_pause_timeout_restores_admission_and_closed_pause_fails():
    receiver = HttpToolReceiver(Backend(), request_timeout=0.15)
    # Simulate a backend that has not honored its deadline, without leaking a thread.
    with receiver._condition:
        receiver._active_operations = 1
    try:
        with pytest.raises(TimeoutError, match="quiesce"):
            with receiver.paused():
                pytest.fail("pause entered before active operation completed")
        assert not receiver.health()["paused"]
    finally:
        with receiver._condition:
            receiver._active_operations = 0
        receiver.close()
    with pytest.raises(RuntimeError, match="closed"):
        with receiver.paused():
            pass
