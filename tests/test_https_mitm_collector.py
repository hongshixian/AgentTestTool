"""Verify run-scoped HTTPS MITM capture without external services."""

from __future__ import annotations

import http.client
import gzip
import ipaddress
import json
import select
import socket
import socketserver
import ssl
import threading
import time
import zlib
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from evidence_collectors.base import (
    CollectionCheckpoint,
    CollectionContext,
    CollectorStatus,
    ObservationWindow,
)
from evidence_collectors.network import HttpsMitmCollector
from evidence_collectors.network.https_mitm import _no_proxy_matches_target


class _TlsServer:
    def __init__(self, tmp_path: Path, handler: type[BaseHTTPRequestHandler]) -> None:
        cert_path, key_path, ca_path = _create_server_certificate(tmp_path)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        context.set_alpn_protocols(["http/1.1"])
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.ca_path = ca_path

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])

    def __enter__(self) -> "_TlsServer":
        self.thread.start()
        return self

    def __exit__(self, *_args) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        assert not self.thread.is_alive()


class _ConnectProxyHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        head = bytearray()
        while b"\r\n\r\n" not in head:
            data = self.request.recv(4096)
            if not data:
                return
            head.extend(data)
        lines = bytes(head).split(b"\r\n")
        method, authority, _ = lines[0].decode("latin1").split(" ", 2)
        assert method == "CONNECT"
        host, port_text = authority.rsplit(":", 1)
        headers = {
            name.decode("latin1").lower(): value.strip().decode("latin1")
            for line in lines[1:]
            if b":" in line
            for name, value in (line.split(b":", 1),)
        }
        self.server.targets.append((host, int(port_text), headers))
        upstream = socket.create_connection((host, int(port_text)), timeout=5)
        try:
            self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            while True:
                readable, _, _ = select.select((self.request, upstream), (), (), 5)
                if not readable:
                    return
                for source in readable:
                    data = source.recv(64 * 1024)
                    if not data:
                        return
                    (upstream if source is self.request else self.request).sendall(data)
        finally:
            upstream.close()


class _ConnectProxy:
    def __init__(self) -> None:
        self.server = socketserver.ThreadingTCPServer(
            ("127.0.0.1", 0), _ConnectProxyHandler
        )
        self.server.daemon_threads = True
        self.server.targets = []
        self.thread = threading.Thread(target=self.server.serve_forever)

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://fixture:password@{host}:{port}"

    def __enter__(self) -> "_ConnectProxy":
        self.thread.start()
        return self

    def __exit__(self, *_args) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        assert not self.thread.is_alive()


class _HealthyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requests: list[tuple[str, bytes]] = []

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        body = self._read_request_body()
        self.requests.append((self.path, body))
        response = (
            b'{"access_token":"response-secret","nested":'
            b'{"client_secret":"response-\\\"secret"},"answer":"ok"}'
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for chunk in (b"data: first\n\n", b"data: second\n\n"):
            self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def _read_request_body(self) -> bytes:
        if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
            result = bytearray()
            while True:
                size = int(self.rfile.readline().split(b";", 1)[0], 16)
                if not size:
                    while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                        pass
                    return bytes(result)
                result.extend(self.rfile.read(size))
                assert self.rfile.read(2) == b"\r\n"
        return self.rfile.read(int(self.headers.get("Content-Length", "0")))

    def log_message(self, *_args) -> None:
        return


class _IncompleteHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        self.send_response(200)
        self.send_header("Content-Length", "20")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(b"short")
        self.wfile.flush()
        self.close_connection = True

    def log_message(self, *_args) -> None:
        return


class _CompressedHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    payloads = {
        "/gzip": ("gzip", gzip.compress(b"G" * 5_000_000)),
        "/deflate": ("deflate", zlib.compress(b"D" * 5_000_000)),
    }

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        encoding, response = self.payloads[self.path]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Encoding", encoding)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        for offset in range(0, len(response), 7):
            self.wfile.write(response[offset : offset + 7])
            self.wfile.flush()

    def log_message(self, *_args) -> None:
        return


def test_prepare_allocates_isolated_proxy_and_run_local_ca(tmp_path) -> None:
    existing_ca = _create_server_certificate(tmp_path / "existing-ca")[2]
    first = _collector(
        base_environment={
            "NODE_EXTRA_CA_CERTS": str(existing_ca),
            "NO_PROXY": "internal.example,localhost",
            "no_proxy": "lower.example",
        }
    )
    second = _collector()
    first_config = first.prepare(_context(tmp_path / "first", "run-1"))
    second_config = second.prepare(_context(tmp_path / "second", "run-2"))

    try:
        assert set(first_config.environment_overrides) == {
            "HTTPS_PROXY",
            "NODE_EXTRA_CA_CERTS",
            "NO_PROXY",
            "no_proxy",
        }
        assert (
            first_config.environment_overrides["HTTPS_PROXY"]
            != second_config.environment_overrides["HTTPS_PROXY"]
        )
        first_ca = Path(first_config.environment_overrides["NODE_EXTRA_CA_CERTS"])
        second_ca = Path(second_config.environment_overrides["NODE_EXTRA_CA_CERTS"])
        assert first_ca.is_file() and second_ca.is_file()
        assert first_ca != second_ca
        assert first_config.environment_overrides["NO_PROXY"] == (
            "internal.example,localhost,lower.example,::1"
        )
        combined_ca = first_ca.read_bytes()
        assert combined_ca.count(b"-----BEGIN CERTIFICATE-----") == 2
    finally:
        first.close()
        second.close()

    assert not first_ca.exists()
    assert not second_ca.exists()


def test_captures_keep_alive_content_length_chunked_and_sse(tmp_path) -> None:
    _HealthyHandler.requests = []
    with _TlsServer(tmp_path / "upstream", _HealthyHandler) as upstream:
        upstream_context = ssl.create_default_context(cafile=str(upstream.ca_path))
        collector = _collector(upstream_ssl_context=upstream_context)
        launch = collector.prepare(_context(tmp_path / "collector", "capture-run"))
        collector.start()
        before = _checkpoint(collector, "before")
        client_context = ssl.create_default_context(
            cafile=launch.environment_overrides["NODE_EXTRA_CA_CERTS"]
        )
        connection = http.client.HTTPSConnection(
            *collector.address, context=client_context, timeout=5
        )
        connection.set_tunnel("127.0.0.1", upstream.port)

        try:
            request_body = (
                b'{"api_key":"body-secret","prompt":"configured-secret",'
                b'"nested":{"client_secret":"body-\\\"secret",'
                b'"user_id":"user-123","safe":"yes"}}'
            )
            connection.request(
                "POST",
                "/v2/chat/completions?token=url-secret&safe=yes",
                body=request_body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer header-secret",
                    "X-Refresh-Token": "refresh-secret",
                    "X-User-Id": "user-123",
                    "X-Account-Id": "account-123",
                    "X-Client-Secret": "client-secret",
                    "X-Credential": "credential-secret",
                    "X-Context": "configured-secret",
                },
            )
            first_response = connection.getresponse()
            assert first_response.status == 200
            assert json.loads(first_response.read())["answer"] == "ok"

            connection.request(
                "POST",
                "/v2/chunked",
                body=[b"first-", b"second"],
                headers={"Content-Type": "text/plain"},
                encode_chunked=True,
            )
            chunked_request_response = connection.getresponse()
            assert chunked_request_response.status == 200
            chunked_request_response.read()

            connection.request("GET", "/v2/events")
            event_response = connection.getresponse()
            assert event_response.status == 200
            assert event_response.read() == b"data: first\n\ndata: second\n\n"
            connection.close()

            drained = collector.drain(3)
            after = _checkpoint(collector, "after")
            result = collector.collect(ObservationWindow(before, after, "agent-turn"))
        finally:
            connection.close()
            ca_path = Path(launch.environment_overrides["NODE_EXTRA_CA_CERTS"])
            thread_name = collector._server_thread.name  # verify owned-thread cleanup
            collector.close()

    assert drained.status is CollectorStatus.AVAILABLE
    assert result.status is CollectorStatus.AVAILABLE
    assert len(result.observations) == 3
    assert [item["sequence"] for item in result.observations] == [1, 2, 3]
    assert json.loads(json.dumps(result.observations)) == list(result.observations)

    first = result.observations[0]
    assert first["scheme"] == "https"
    assert first["host"] == "127.0.0.1"
    assert first["port"] == upstream.port
    assert first["method"] == "POST"
    assert first["path"] == "/v2/chat/completions?token=%3Credacted%3E&safe=yes"
    assert first["request_headers"]["authorization"] == "<redacted>"
    assert first["request_headers"]["x-refresh-token"] == "<redacted>"
    assert first["request_headers"]["x-user-id"] == "<redacted>"
    assert first["request_headers"]["x-account-id"] == "<redacted>"
    assert first["request_headers"]["x-client-secret"] == "<redacted>"
    assert first["request_headers"]["x-credential"] == "<redacted>"
    assert first["request_headers"]["x-context"] == "<redacted>"
    request_payload = json.loads(first["request_body"])
    assert request_payload == {
        "api_key": "<redacted>",
        "prompt": "<redacted>",
        "nested": {
            "client_secret": "<redacted>",
            "user_id": "<redacted>",
            "safe": "yes",
        },
    }
    assert json.loads(first["response_body"]) == {
        "access_token": "<redacted>",
        "nested": {"client_secret": "<redacted>"},
        "answer": "ok",
    }
    assert first["request_complete"] is True
    assert first["response_complete"] is True
    assert first["error"] is None
    assert first["request_body_truncated"] is False

    second = result.observations[1]
    assert second["request_body"] == "first-second"
    assert _HealthyHandler.requests[1] == ("/v2/chunked", b"first-second")

    third = result.observations[2]
    assert third["response_headers"]["transfer-encoding"] == "chunked"
    assert third["response_body"] == "data: first\n\ndata: second\n\n"
    assert not ca_path.exists()
    assert not any(thread.name == thread_name for thread in threading.enumerate())


def test_limits_captured_body_without_truncating_forwarded_traffic(tmp_path) -> None:
    _HealthyHandler.requests = []
    with _TlsServer(tmp_path / "upstream", _HealthyHandler) as upstream:
        upstream_context = ssl.create_default_context(cafile=str(upstream.ca_path))
        collector = _collector(
            max_body_bytes=8, upstream_ssl_context=upstream_context
        )
        launch = collector.prepare(_context(tmp_path / "collector", "bounded-run"))
        collector.start()
        client = _client(collector, launch, upstream.port)
        try:
            client.request("POST", "/bounded", body=b"0123456789abcdef")
            response = client.getresponse()
            response.read()
            result = collector.drain(3)
        finally:
            client.close()
            collector.close()

    observation = result.observations[0]
    assert result.status is CollectorStatus.UNVERIFIED
    assert result.health.healthy is False
    assert "truncated" in result.health.detail
    assert _HealthyHandler.requests[0][1] == b"0123456789abcdef"
    assert observation["request_body"] == "01234567"
    assert observation["request_body_bytes"] == 16
    assert observation["request_body_truncated"] is True
    assert observation["response_body_truncated"] is True


def test_marks_incomplete_response_as_explicit_error(tmp_path) -> None:
    with _TlsServer(tmp_path / "upstream", _IncompleteHandler) as upstream:
        upstream_context = ssl.create_default_context(cafile=str(upstream.ca_path))
        collector = _collector(upstream_ssl_context=upstream_context)
        launch = collector.prepare(_context(tmp_path / "collector", "failure-run"))
        collector.start()
        client = _client(collector, launch, upstream.port)
        try:
            client.request("GET", "/incomplete")
            response = client.getresponse()
            with pytest.raises(http.client.IncompleteRead):
                response.read()
            result = collector.drain(3)
        finally:
            client.close()
            collector.close()

    assert result.status is CollectorStatus.ERROR
    assert result.health.healthy is False
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation["request_complete"] is True
    assert observation["response_complete"] is False
    assert observation["error"].startswith("EOFError:")


def test_tls_rejection_is_a_collector_error_not_missing_evidence(tmp_path) -> None:
    with _TlsServer(tmp_path / "upstream", _HealthyHandler) as upstream:
        upstream_context = ssl.create_default_context(cafile=str(upstream.ca_path))
        collector = _collector(upstream_ssl_context=upstream_context)
        collector.prepare(_context(tmp_path / "collector", "untrusted-ca-run"))
        collector.start()
        untrusted_client = http.client.HTTPSConnection(
            *collector.address, context=ssl.create_default_context(), timeout=5
        )
        untrusted_client.set_tunnel("127.0.0.1", upstream.port)
        try:
            with pytest.raises(ssl.SSLCertVerificationError):
                untrusted_client.request("GET", "/rejected")
            untrusted_client.close()
            # The handler records the TLS failure after the client observes it.
            for _ in range(100):
                result = collector.drain(1)
                if result.status is CollectorStatus.ERROR:
                    break
                threading.Event().wait(0.01)
        finally:
            untrusted_client.close()
            collector.close()

    assert result.status is CollectorStatus.ERROR
    assert result.observations == ()
    assert result.health.healthy is False


def test_removes_all_no_proxy_forms_that_can_bypass_mitm_target(tmp_path) -> None:
    collector = HttpsMitmCollector(
        mitm_hosts=("copilot.tencent.com",),
        base_environment={
            "NO_PROXY": (
                "*,copilot.tencent.com,copilot.tencent.com:443,.tencent.com,"
                "*.tencent.com,tencent.com,safe.example"
            ),
            "no_proxy": ".copilot.tencent.com,api.safe.example,localhost",
        },
    )
    launch = collector.prepare(_context(tmp_path / "collector", "no-proxy-run"))
    try:
        expected = "safe.example,api.safe.example,localhost,127.0.0.1,::1"
        assert launch.environment_overrides["NO_PROXY"] == expected
        assert launch.environment_overrides["no_proxy"] == expected
        assert "copilot.tencent.com" not in expected
        assert "tencent.com" not in expected
        assert "*" not in expected
    finally:
        collector.close()


def test_stream_decompresses_gzip_and_deflate_with_decoded_output_limit(
    tmp_path,
) -> None:
    with _TlsServer(tmp_path / "upstream", _CompressedHandler) as upstream:
        upstream_context = ssl.create_default_context(cafile=str(upstream.ca_path))
        collector = _collector(
            max_body_bytes=64,
            upstream_ssl_context=upstream_context,
        )
        launch = collector.prepare(_context(tmp_path / "collector", "compressed-run"))
        collector.start()
        client = _client(collector, launch, upstream.port)
        try:
            for path, decoder in (("/gzip", gzip.decompress), ("/deflate", zlib.decompress)):
                client.request("GET", path)
                response = client.getresponse()
                wire_body = response.read()
                assert len(decoder(wire_body)) == 5_000_000
            result = collector.drain(3)
        finally:
            client.close()
            collector.close()

    assert result.status is CollectorStatus.UNVERIFIED
    assert len(result.observations) == 2
    for observation, expected in zip(result.observations, ("G", "D"), strict=True):
        assert observation["response_body"] == expected * 64
        # The collector decodes only one byte beyond the retained limit, so a
        # compression bomb cannot force it to process the full expanded body.
        assert observation["response_body_bytes"] == 65
        assert observation["response_wire_bytes"] < 10_000
        assert observation["response_body_truncated"] is True
        assert observation["response_complete"] is True
        assert observation["error"] is None


def test_run_scoped_connection_and_exchange_limits_fail_closed(tmp_path) -> None:
    connection_limited = _collector(max_connections=1)
    connection_limited.prepare(_context(tmp_path / "connections", "connection-limit"))
    connection_limited.start()
    first = socket.create_connection(connection_limited.address, timeout=3)
    try:
        for _ in range(100):
            if connection_limited._active_connections == 1:
                break
            time.sleep(0.01)
        baseline_workers = sum(
            "process_request_thread" in thread.name for thread in threading.enumerate()
        )
        for _ in range(12):
            rejected = socket.create_connection(connection_limited.address, timeout=3)
            try:
                assert b"503 Service Unavailable" in rejected.recv(4096)
            finally:
                rejected.close()
        assert connection_limited._active_connections == 1
        assert sum(
            "process_request_thread" in thread.name for thread in threading.enumerate()
        ) == baseline_workers
        first.close()
        connection_result = connection_limited.drain(3)
    finally:
        first.close()
        connection_limited.close()

    assert connection_result.status is CollectorStatus.UNVERIFIED
    assert "connections" in connection_result.health.detail

    _HealthyHandler.requests = []
    with _TlsServer(tmp_path / "upstream", _HealthyHandler) as upstream:
        upstream_context = ssl.create_default_context(cafile=str(upstream.ca_path))
        exchange_limited = _collector(
            max_exchanges=1,
            upstream_ssl_context=upstream_context,
        )
        launch = exchange_limited.prepare(
            _context(tmp_path / "exchanges", "exchange-limit")
        )
        exchange_limited.start()
        client = _client(exchange_limited, launch, upstream.port)
        try:
            client.request("GET", "/first")
            assert client.getresponse().read() == b"data: first\n\ndata: second\n\n"
            client.request("GET", "/second")
            second_response = client.getresponse()
            assert second_response.status == 503
            second_response.read()
            exchange_result = exchange_limited.drain(3)
        finally:
            client.close()
            exchange_limited.close()

    assert exchange_result.status is CollectorStatus.UNVERIFIED
    assert len(exchange_result.observations) == 1
    assert "exchanges" in exchange_result.health.detail


def test_certificate_cache_and_error_diagnostics_are_bounded(tmp_path) -> None:
    collector = _collector(max_certificate_cache=1, max_error_records=1)
    collector.prepare(_context(tmp_path / "collector", "metadata-limits"))
    collector.start()
    try:
        collector._server_context_for("127.0.0.1")
        with pytest.raises(RuntimeError, match="certificate cache"):
            collector._server_context_for("localhost")
        collector._record_collector_error("first")
        collector._record_collector_error("second")
        collector._record_collector_error("third")
        result = collector.drain(3)
        assert len(collector._certificate_contexts) == 1
        assert len(collector._errors) == 1
        assert collector._dropped_error_count == 2
    finally:
        collector.close()

    assert result.status is CollectorStatus.ERROR
    assert result.health.lost_record_count >= 3
    assert any("retention limit" in item for item in result.limitations)


def test_error_before_checkpoint_does_not_poison_a_later_window(tmp_path) -> None:
    collector = _collector()
    collector.prepare(_context(tmp_path / "collector", "scoped-error-run"))
    collector.start()
    try:
        collector._record_collector_error("fixture-before-window")
        before = _checkpoint(collector, "before")
        after = _checkpoint(collector, "after")
        result = collector.collect(ObservationWindow(before, after, "clean-window"))
    finally:
        collector.close()

    assert result.status is CollectorStatus.MISSING
    assert result.health.healthy


def test_resource_limit_is_scoped_to_the_window_where_it_occurred(tmp_path) -> None:
    collector = _collector()
    collector.prepare(_context(tmp_path / "collector", "scoped-limit-run"))
    collector.start()
    try:
        before = _checkpoint(collector, "limited-before")
        with collector._condition:
            collector._record_resource_limit_locked("connections")
        after = _checkpoint(collector, "limited-after")
        limited = collector.collect(
            ObservationWindow(before, after, "limited-window")
        )

        clean_before = _checkpoint(collector, "clean-before")
        clean_after = _checkpoint(collector, "clean-after")
        clean = collector.collect(
            ObservationWindow(clean_before, clean_after, "clean-window")
        )
    finally:
        collector.close()

    assert limited.status is CollectorStatus.UNVERIFIED
    assert limited.diagnostics["resource_limits"] == ("connections",)
    assert clean.status is CollectorStatus.MISSING
    assert clean.health.healthy
    assert clean.diagnostics["resource_limits"] == ()


def test_dropped_errors_before_checkpoint_do_not_poison_later_window(tmp_path) -> None:
    collector = _collector(max_error_records=1)
    collector.prepare(_context(tmp_path / "collector", "scoped-dropped-run"))
    collector.start()
    try:
        collector._record_collector_error("retained-before-window")
        collector._record_collector_error("dropped-before-window")
        before = _checkpoint(collector, "before")
        after = _checkpoint(collector, "after")
        result = collector.collect(ObservationWindow(before, after, "clean-window"))
    finally:
        collector.close()

    assert result.status is CollectorStatus.MISSING
    assert result.health.healthy
    assert result.diagnostics["dropped_error_count"] == 0


def test_uses_existing_http_proxy_as_upstream_connect_proxy(tmp_path) -> None:
    with _TlsServer(tmp_path / "upstream", _HealthyHandler) as upstream:
        upstream_context = ssl.create_default_context(cafile=str(upstream.ca_path))
        with _ConnectProxy() as proxy:
            collector = _collector(
                base_environment={"HTTPS_PROXY": proxy.url},
                upstream_ssl_context=upstream_context,
            )
            launch = collector.prepare(_context(tmp_path / "collector", "proxy-run"))
            collector.start()
            client = _client(collector, launch, upstream.port)
            try:
                client.request("GET", "/through-upstream-proxy")
                response = client.getresponse()
                assert response.status == 200
                response.read()
                client.close()
                result = collector.drain(3)
            finally:
                client.close()
                collector.close()

    assert result.status is CollectorStatus.AVAILABLE
    assert proxy.server.targets[0][:2] == ("127.0.0.1", upstream.port)
    assert proxy.server.targets[0][2]["proxy-authorization"].startswith("Basic ")


@pytest.mark.parametrize(
    "entry",
    [
        "*",
        "copilot.tencent.com",
        "copilot.tencent.com:443",
        "tencent.com",
        ".tencent.com",
        "*.tencent.com",
        "*copilot.tencent.com",
    ],
)
def test_original_no_proxy_matching_forms_are_recognized(entry) -> None:
    assert _no_proxy_matches_target(entry, "copilot.tencent.com", 443)


def test_original_no_proxy_port_constraint_is_preserved() -> None:
    assert _no_proxy_matches_target("copilot.tencent.com:443", "copilot.tencent.com", 443)
    assert not _no_proxy_matches_target(
        "copilot.tencent.com:8443", "copilot.tencent.com", 443
    )


def test_original_no_proxy_bypasses_upstream_proxy_inside_collector(tmp_path) -> None:
    with _TlsServer(tmp_path / "upstream", _HealthyHandler) as upstream:
        upstream_context = ssl.create_default_context(cafile=str(upstream.ca_path))
        with _ConnectProxy() as proxy:
            for index, bypass in enumerate(
                ("*", "127.0.0.1", f"127.0.0.1:{upstream.port}"), start=1
            ):
                targets_before = len(proxy.server.targets)
                collector = _collector(
                    base_environment={
                        "HTTPS_PROXY": proxy.url,
                        "NO_PROXY": bypass,
                    },
                    upstream_ssl_context=upstream_context,
                )
                launch = collector.prepare(
                    _context(tmp_path / f"collector-{index}", f"bypass-run-{index}")
                )
                # The Agent must still enter the local collector; only the
                # collector's own upstream connection preserves this bypass.
                assert bypass not in launch.environment_overrides["NO_PROXY"]
                collector.start()
                client = _client(collector, launch, upstream.port)
                try:
                    client.request("GET", f"/direct-{index}")
                    response = client.getresponse()
                    assert response.status == 200
                    response.read()
                    result = collector.drain(3)
                finally:
                    client.close()
                    collector.close()
                assert result.status is CollectorStatus.AVAILABLE
                assert len(proxy.server.targets) == targets_before


def test_non_allowlisted_host_is_tunnelled_without_tls_interception(tmp_path) -> None:
    with _TlsServer(tmp_path / "upstream", _HealthyHandler) as upstream:
        collector = HttpsMitmCollector(
            mitm_hosts=("copilot.tencent.com",),
            base_environment={},
        )
        launch = collector.prepare(_context(tmp_path / "collector", "tunnel-run"))
        collector.start()
        client_context = ssl.create_default_context(cafile=str(upstream.ca_path))
        client = http.client.HTTPSConnection(
            *collector.address, context=client_context, timeout=5
        )
        client.set_tunnel("127.0.0.1", upstream.port)
        try:
            client.request("GET", "/passthrough")
            response = client.getresponse()
            assert response.status == 200
            response.read()
            client.close()
            result = collector.drain(3)
        finally:
            client.close()
            collector.close()

    assert result.status is CollectorStatus.AVAILABLE
    assert len(result.observations) == 1
    assert result.observations[0]["scheme"] == "connect"
    assert result.observations[0]["intercepted"] is False
    assert result.observations[0]["request_body"] == ""
    assert result.observations[0]["response_body"] == ""


def test_rejects_unsupported_upstream_proxy_before_allocating_resources(
    tmp_path,
) -> None:
    collector = _collector(
        base_environment={"HTTPS_PROXY": "https://proxy.example:8443"}
    )

    with pytest.raises(ValueError, match="must use an http"):
        collector.prepare(_context(tmp_path / "collector", "bad-proxy-run"))

    assert collector._temp_dir is None
    collector.close()


def test_redacts_sensitive_json_embedded_in_stream_text(tmp_path) -> None:
    collector = _collector()
    collector.prepare(_context(tmp_path / "collector", "stream-redaction-run"))
    try:
        redacted = collector._redact_text(
            'data: {"nested":{"client_secret":"value-\\\"suffix",'
            '"userId":"user-123"},"max_tokens":128}'
        )
    finally:
        collector.close()

    assert "value-" not in redacted
    assert "suffix" not in redacted
    assert "user-123" not in redacted
    assert '"max_tokens":128' in redacted


def test_redacts_mixed_and_truncated_sse_lines_conservatively(tmp_path) -> None:
    collector = _collector()
    collector.prepare(_context(tmp_path / "collector", "partial-sse-redaction"))
    try:
        redacted = collector._redact_text(
            'data: {"safe":"ok","max_tokens":128}\n'
            'data: {"client_secret":"malformed-secret"\n'
            'event: message\n'
            'data: {"nested":true,"client_secret":"partial-sensitive-tail'
        )
    finally:
        collector.close()

    assert "malformed-secret" not in redacted
    assert "partial-sensitive-tail" not in redacted
    assert redacted.count("<redacted>") >= 2
    assert '"max_tokens":128' in redacted
    assert '"safe":"ok"' in redacted


def test_redacts_sensitive_json_split_across_sse_data_lines(tmp_path) -> None:
    collector = _collector()
    collector.prepare(_context(tmp_path / "collector", "multiline-sse-redaction"))
    try:
        redacted = collector._redact_text(
            "event: message\n"
            'data: {"client_secret":\n'
            'data: "CROSS-LINE-LEAK","safe":"ok"}\n'
            "\n"
            "data: ordinary first line\n"
            "data: ordinary second line\n"
            "\n"
            "data: [DONE]\n"
            "\n"
        )
    finally:
        collector.close()

    assert "CROSS-LINE-LEAK" not in redacted
    assert 'data: {"client_secret":"<redacted>","safe":"ok"}' in redacted
    assert "data: ordinary first line\ndata: ordinary second line" in redacted
    assert "data: [DONE]\n\n" in redacted


def test_close_failure_can_be_retried_and_then_removes_ca(tmp_path, monkeypatch) -> None:
    collector = _collector()
    launch = collector.prepare(_context(tmp_path / "collector", "retry-close-run"))
    ca_path = Path(launch.environment_overrides["NODE_EXTRA_CA_CERTS"])
    assert collector._temp_dir is not None
    original_cleanup = collector._temp_dir.cleanup
    attempts = 0

    def flaky_cleanup() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("fixture cleanup failure")
        original_cleanup()

    monkeypatch.setattr(collector._temp_dir, "cleanup", flaky_cleanup)

    with pytest.raises(BaseExceptionGroup, match="cleanup failed"):
        collector.close()

    assert ca_path.exists()
    assert collector._closed is False
    collector.close()
    assert attempts == 2
    assert collector._closed is True
    assert not ca_path.exists()


def _client(
    collector: HttpsMitmCollector,
    launch,
    upstream_port: int,
) -> http.client.HTTPSConnection:
    context = ssl.create_default_context(
        cafile=launch.environment_overrides["NODE_EXTRA_CA_CERTS"]
    )
    client = http.client.HTTPSConnection(*collector.address, context=context, timeout=5)
    client.set_tunnel("127.0.0.1", upstream_port)
    return client


def _collector(**kwargs) -> HttpsMitmCollector:
    kwargs.setdefault("mitm_hosts", ("127.0.0.1",))
    kwargs.setdefault("base_environment", {})
    return HttpsMitmCollector(**kwargs)


def _context(root: Path, run_id: str) -> CollectionContext:
    workspace = root / "workspace"
    evidence = root / "evidence"
    workspace.mkdir(parents=True)
    evidence.mkdir(parents=True)
    return CollectionContext(
        run_id=run_id,
        test_case_id="ATS-NETWORK-01",
        product="codebuddy",
        workspace=workspace,
        evidence_dir=evidence,
        secrets=("configured-secret",),
    )


def _checkpoint(collector: HttpsMitmCollector, label: str) -> CollectionCheckpoint:
    cursor = collector.checkpoint(label)
    return CollectionCheckpoint(label, {collector.name: cursor})


def _create_server_certificate(directory: Path) -> tuple[Path, Path, Path]:
    directory.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Local Test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
        .sign(ca_key, hashes.SHA256())
    )
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_name)
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            False,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
        .sign(ca_key, hashes.SHA256())
    )
    ca_path = directory / "ca.pem"
    cert_path = directory / "server.pem"
    key_path = directory / "server.key"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path, ca_path
