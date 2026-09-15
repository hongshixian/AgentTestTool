"""Run-scoped HTTP/1.1 CONNECT proxy for black-box HTTPS evidence capture."""

from __future__ import annotations

import fnmatch
import ipaddress
import json
import os
import re
import select
import socket
import socketserver
import ssl
import tempfile
import threading
import time
import uuid
import zlib
from base64 import b64encode
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from evidence_collectors.base import (
    CollectionContext,
    CollectorHealth,
    CollectorHealthState,
    CollectorLaunchConfig,
    CollectorResult,
    CollectorStatus,
    EvidenceCollector,
    EvidenceCursor,
    ObservationWindow,
    utc_now,
)


_HEADER_LIMIT = 128 * 1024
_IO_CHUNK_SIZE = 64 * 1024
_SENSITIVE_NAME = re.compile(
    r"(?i)(?:^|[_-])(?:token|api[_-]?key|authorization|password|passwd|secret|"
    r"credential|cookie|user[_-]?id|account[_-]?id|email)(?:$|[_-])"
)
_JSON_FIELD_ASSIGNMENT = re.compile(
    r'(?P<prefix>(?P<key>"(?:\\.|[^"\\])*")\s*:\s*)'
    r'(?P<value>"(?:\\.|[^"\\])*"|[^,}\]\r\n]+)'
)
_TEXT_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b((?:client[_-]?)?(?:token|secret)|api[_-]?key|authorization|password|"
    r"passwd|credential|cookie|user[_-]?id|account[_-]?id|email)"
    r"(\s*[:=]\s*)([^\s,;&]+)"
)
_BEARER_CREDENTIAL = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
_CA_BUNDLE_LIMIT = 16 * 1024 * 1024


class _ResourceLimitReached(RuntimeError):
    """Stop collection when a run-scoped resource budget is exhausted."""


@dataclass(frozen=True, slots=True)
class _UpstreamProxy:
    host: str
    port: int
    authorization: str | None = field(default=None, repr=False)


def _encode_cursor_state(
    sequence: int,
    error_count: int,
    dropped_error_count: int,
    resource_limit_counts: Mapping[str, int],
) -> str:
    return json.dumps(
        [
            sequence,
            error_count,
            dropped_error_count,
            sorted(resource_limit_counts.items()),
        ],
        separators=(",", ":"),
    )


def _decode_cursor_state(value: str) -> tuple[int, int, int, dict[str, int]]:
    try:
        sequence, error_count, dropped_error_count, raw_limits = json.loads(value)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("HTTPS MITM cursor state is invalid") from exc
    counters = (sequence, error_count, dropped_error_count)
    if any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for item in counters
    ):
        raise ValueError("HTTPS MITM cursor counters must be non-negative integers")
    if not isinstance(raw_limits, list):
        raise ValueError("HTTPS MITM cursor resource limits are invalid")
    limits: dict[str, int] = {}
    for item in raw_limits:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not item[0]
            or isinstance(item[1], bool)
            or not isinstance(item[1], int)
            or item[1] < 0
        ):
            raise ValueError("HTTPS MITM cursor resource limits are invalid")
        limits[item[0]] = item[1]
    return sequence, error_count, dropped_error_count, limits


def _format_authority(host: str, port: int) -> str:
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


def _parse_upstream_proxy(value: str | None) -> _UpstreamProxy | None:
    if value is None or not value.strip():
        return None
    raw = value.strip()
    parsed = urlsplit(raw if "://" in raw else f"http://{raw}")
    if parsed.scheme.lower() != "http":
        raise ValueError("HTTPS_PROXY upstream must use an http:// CONNECT proxy")
    if not parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("HTTPS_PROXY upstream URL is invalid")
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise ValueError("HTTPS_PROXY upstream port is invalid") from exc
    authorization = None
    if parsed.username is not None:
        username = unquote(parsed.username)
        password = unquote(parsed.password or "")
        encoded = b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        authorization = f"Basic {encoded}"
    return _UpstreamProxy(parsed.hostname, port, authorization)


def _merge_no_proxy(*values: str) -> str:
    entries: list[str] = []
    seen: set[str] = set()
    for value in values:
        for entry in value.split(","):
            normalized = entry.strip()
            key = normalized.casefold()
            if normalized and key not in seen:
                seen.add(key)
                entries.append(normalized)
    return ",".join(entries)


def _no_proxy_matches_target(entry: str, host: str, port: int | None) -> bool:
    """Apply the common NO_PROXY host matching forms conservatively."""

    candidate = entry.strip().casefold()
    target = host.strip().casefold().rstrip(".")
    candidate_port: int | None = None
    if not candidate:
        return False
    if candidate == "*":
        return True
    if "://" in candidate:
        parsed = urlsplit(candidate)
        candidate = (parsed.hostname or candidate).casefold()
        try:
            candidate_port = parsed.port
        except ValueError:
            return False
    elif candidate.startswith("[") and "]" in candidate:
        closing = candidate.index("]")
        remainder = candidate[closing + 1 :]
        if remainder.startswith(":") and remainder[1:].isdigit():
            candidate_port = int(remainder[1:])
        candidate = candidate[1:closing]
    elif candidate.count(":") == 1 and candidate.rsplit(":", 1)[1].isdigit():
        candidate, raw_port = candidate.rsplit(":", 1)
        candidate_port = int(raw_port)
    if port is not None and candidate_port is not None and candidate_port != port:
        return False
    candidate = candidate.rstrip(".")
    try:
        network = ipaddress.ip_network(candidate, strict=False)
        return ipaddress.ip_address(target) in network
    except ValueError:
        pass
    if "*" in candidate:
        return fnmatch.fnmatchcase(target, candidate.lstrip("."))
    suffix = candidate.lstrip(".")
    return target == suffix or target.endswith("." + suffix)


def _safe_no_proxy(values: Iterable[str], intercepted_hosts: Iterable[str]) -> str:
    merged = _merge_no_proxy(*values)
    hosts = tuple(intercepted_hosts)
    return _merge_no_proxy(
        ",".join(
            entry
            for entry in merged.split(",")
            if entry
            and not any(_no_proxy_matches_target(entry, host, None) for host in hosts)
        )
    )


def _is_sensitive_name(value: str) -> bool:
    snake_case = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    return _SENSITIVE_NAME.search(snake_case) is not None


def _iso_now() -> str:
    return utc_now().isoformat()


def _parse_authority(authority: str) -> tuple[str, int]:
    if authority.startswith("["):
        closing = authority.find("]")
        if closing < 0:
            raise ValueError("invalid IPv6 CONNECT authority")
        host = authority[1:closing]
        remainder = authority[closing + 1 :]
        port = int(remainder[1:]) if remainder.startswith(":") else 443
        return host, port
    host, separator, raw_port = authority.rpartition(":")
    if separator and raw_port.isdigit():
        return host, int(raw_port)
    return authority, 443


def _header_map(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in headers:
        if name in result:
            result[name] = f"{result[name]}, {value}"
        else:
            result[name] = value
    return result


class _BufferedSocket:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.buffer = bytearray()

    def read_until(self, delimiter: bytes, limit: int) -> bytes:
        while True:
            index = self.buffer.find(delimiter)
            if index >= 0:
                end = index + len(delimiter)
                result = bytes(self.buffer[:end])
                del self.buffer[:end]
                return result
            if len(self.buffer) >= limit:
                raise ValueError("HTTP header exceeded the configured limit")
            data = self.sock.recv(min(_IO_CHUNK_SIZE, limit - len(self.buffer)))
            if not data:
                if not self.buffer:
                    return b""
                raise EOFError("connection closed before HTTP framing completed")
            self.buffer.extend(data)

    def read_exact(self, size: int) -> bytes:
        while len(self.buffer) < size:
            data = self.sock.recv(min(_IO_CHUNK_SIZE, size - len(self.buffer)))
            if not data:
                raise EOFError("connection closed before HTTP body completed")
            self.buffer.extend(data)
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    def read_some(self, size: int = _IO_CHUNK_SIZE) -> bytes:
        if self.buffer:
            result = bytes(self.buffer[:size])
            del self.buffer[:size]
            return result
        return self.sock.recv(size)


class _CaptureBuffer:
    """Keep bounded decoded bytes while the unchanged wire body is forwarded."""

    def __init__(self, limit: int, content_encoding: str = "") -> None:
        self.limit = limit
        self.data = bytearray()
        self.total_bytes = 0
        self.wire_bytes = 0
        self.truncated = False
        self.decode_error: str | None = None
        self._decompression_stopped = False
        encoding = content_encoding.split(",", 1)[0].strip().casefold()
        if encoding == "gzip":
            self._decompressor: Any | None = zlib.decompressobj(16 + zlib.MAX_WBITS)
        elif encoding == "deflate":
            self._decompressor = zlib.decompressobj()
        else:
            self._decompressor = None

    def append(self, data: bytes) -> None:
        self.wire_bytes += len(data)
        if self._decompressor is None:
            self._append_decoded(data)
            return
        if self.decode_error is not None or self._decompression_stopped:
            return
        pending = data
        try:
            while pending and not self._decompression_stopped:
                remaining = max(0, self.limit - len(self.data))
                decoded = self._decompressor.decompress(pending, remaining + 1)
                self._append_decoded(decoded)
                if self.truncated:
                    self._decompression_stopped = True
                    return
                previous = pending
                pending = self._decompressor.unconsumed_tail
                if pending == previous and not decoded:
                    self.decode_error = "compressed body decoder made no progress"
                    return
        except zlib.error as exc:
            self.decode_error = f"zlib.error: {str(exc)[:160]}"

    def finish(self) -> None:
        if (
            self._decompressor is None
            or self.decode_error is not None
            or self._decompression_stopped
        ):
            return
        try:
            while True:
                remaining = max(0, self.limit - len(self.data))
                decoded = self._decompressor.decompress(b"", remaining + 1)
                if not decoded:
                    break
                self._append_decoded(decoded)
                if self.truncated:
                    self._decompression_stopped = True
                    return
            if not self._decompressor.eof:
                self.decode_error = "compressed body ended before stream completion"
        except zlib.error as exc:
            self.decode_error = f"zlib.error: {str(exc)[:160]}"

    def _append_decoded(self, data: bytes) -> None:
        self.total_bytes += len(data)
        remaining = self.limit - len(self.data)
        if remaining > 0:
            self.data.extend(data[:remaining])
        if len(data) > remaining:
            self.truncated = True


class _ProxyServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = False
    block_on_close = True

    def __init__(self, collector: "HttpsMitmCollector") -> None:
        self.collector = collector
        super().__init__(("127.0.0.1", 0), _ProxyHandler)

    def process_request(self, request: socket.socket, client_address: Any) -> None:
        """Reserve a bounded worker slot before ThreadingMixIn starts a thread."""

        if not self.collector._reserve_connection():
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n"
                    b"Connection: close\r\n\r\n"
                )
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.collector._release_connection()
            raise


class _ProxyHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        collector = self.server.collector
        collector._register_socket(self.request)
        try:
            collector._handle_client(self.request)
        except _ResourceLimitReached:
            return
        except (ConnectionError, EOFError, OSError, ssl.SSLError) as exc:
            # A clean keep-alive close returns an empty header block. Exceptions
            # before an exchange (TLS rejection, unreachable upstream, malformed
            # CONNECT) are collection failures and must never look like no traffic.
            if not collector._stopping:
                collector._record_collector_error(type(exc).__name__)
        except Exception as exc:  # pragma: no cover - defensive server boundary
            if not collector._stopping:
                collector._record_collector_error(type(exc).__name__)
        finally:
            collector._unregister_socket(self.request)
            collector._release_connection()


class HttpsMitmCollector(EvidenceCollector):
    """Capture HTTPS exchanges from one managed Agent process.

    The collector terminates CONNECT tunnels with a run-local CA and immediately
    forwards the unchanged HTTP body to the real upstream. Only bounded,
    redacted observations are retained. It intentionally supports HTTP/1.1 only;
    ALPN is forced on both TLS legs so framing and completeness are auditable.
    """

    def __init__(
        self,
        *,
        max_body_bytes: int = 1024 * 1024,
        socket_timeout_seconds: float = 60.0,
        no_proxy: str = "127.0.0.1,localhost,::1",
        mitm_hosts: Iterable[str] = ("copilot.tencent.com",),
        base_environment: Mapping[str, str] | None = None,
        upstream_ssl_context: ssl.SSLContext | None = None,
        max_connections: int = 512,
        max_exchanges: int = 10_000,
        max_certificate_cache: int = 128,
        max_error_records: int = 128,
    ) -> None:
        if isinstance(max_body_bytes, bool) or max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        if isinstance(socket_timeout_seconds, bool) or socket_timeout_seconds <= 0:
            raise ValueError("socket_timeout_seconds must be positive")
        if not no_proxy.strip():
            raise ValueError("no_proxy must be nonempty")
        normalized_hosts = frozenset(
            host.strip().casefold().rstrip(".") for host in mitm_hosts
        )
        if not normalized_hosts or any(not host for host in normalized_hosts):
            raise ValueError("mitm_hosts must contain nonempty host names")
        if any("*" in host or ":" in host for host in normalized_hosts):
            raise ValueError("mitm_hosts only supports exact host names")
        limits = (
            max_connections,
            max_exchanges,
            max_certificate_cache,
            max_error_records,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in limits
        ):
            raise ValueError("collector run limits must be positive integers")
        self._max_body_bytes = int(max_body_bytes)
        self._socket_timeout = float(socket_timeout_seconds)
        self._no_proxy = no_proxy
        self._mitm_hosts = normalized_hosts
        self._base_environment = (
            None if base_environment is None else dict(base_environment)
        )
        self._upstream_proxy: _UpstreamProxy | None = None
        self._upstream_no_proxy: tuple[str, ...] = ()
        self._upstream_ssl_context = upstream_ssl_context
        self._max_connections = max_connections
        self._max_exchanges = max_exchanges
        self._max_certificate_cache = max_certificate_cache
        self._max_error_records = max_error_records
        self._context: CollectionContext | None = None
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._ca_key: rsa.RSAPrivateKey | None = None
        self._ca_cert: x509.Certificate | None = None
        self._ca_path: Path | None = None
        self._server: _ProxyServer | None = None
        self._server_thread: threading.Thread | None = None
        self._certificate_contexts: dict[str, ssl.SSLContext] = {}
        self._certificate_reservations: set[str] = set()
        self._observations: list[dict[str, Any]] = []
        self._sequence = 0
        self._connection_count = 0
        self._active_connections = 0
        self._exchange_count = 0
        self._active_exchanges = 0
        self._errors: list[tuple[int, str]] = []
        self._error_count = 0
        self._dropped_error_count = 0
        self._resource_limit_counts: dict[str, int] = {}
        self._open_sockets: set[socket.socket] = set()
        self._condition = threading.Condition()
        self._prepared = False
        self._started = False
        self._stopping = False
        self._server_shutdown = False
        self._closed = False

    @property
    def name(self) -> str:
        return "https_mitm"

    @property
    def address(self) -> tuple[str, int]:
        if self._server is None:
            raise RuntimeError("collector has not been prepared")
        host, port = self._server.server_address
        return str(host), int(port)

    def prepare(self, context: CollectionContext) -> CollectorLaunchConfig:
        if self._prepared or self._closed:
            raise RuntimeError("collector can only be prepared once")
        environment = (
            os.environ if self._base_environment is None else self._base_environment
        )
        upper_proxy = environment.get("HTTPS_PROXY", "").strip()
        lower_proxy = environment.get("https_proxy", "").strip()
        if upper_proxy and lower_proxy and upper_proxy != lower_proxy:
            raise ValueError("HTTPS_PROXY and https_proxy disagree")
        existing_proxy = upper_proxy or lower_proxy
        self._upstream_proxy = _parse_upstream_proxy(existing_proxy)
        original_no_proxy = _merge_no_proxy(
            environment.get("NO_PROXY", ""),
            environment.get("no_proxy", ""),
        )
        self._upstream_no_proxy = tuple(
            entry for entry in original_no_proxy.split(",") if entry
        )
        self._context = context
        self._temp_dir = tempfile.TemporaryDirectory(
            prefix=f"agent-test-mitm-{context.run_id[:24]}-"
        )
        directory = Path(self._temp_dir.name)
        self._create_ca(directory)
        self._merge_ca_bundle(
            directory,
            environment.get("NODE_EXTRA_CA_CERTS"),
        )
        self._server = _ProxyServer(self)
        self._prepared = True
        proxy = f"http://127.0.0.1:{self.address[1]}"
        merged_no_proxy = _safe_no_proxy(
            (
                original_no_proxy,
                self._no_proxy,
            ),
            self._mitm_hosts,
        )
        overrides = {
            "HTTPS_PROXY": proxy,
            "NODE_EXTRA_CA_CERTS": str(self._ca_path),
            "NO_PROXY": merged_no_proxy,
        }
        if "https_proxy" in environment:
            overrides["https_proxy"] = proxy
        if "no_proxy" in environment:
            overrides["no_proxy"] = merged_no_proxy
        return CollectorLaunchConfig(overrides)

    def start(self) -> None:
        if not self._prepared or self._server is None:
            raise RuntimeError("collector must be prepared before start")
        if self._started or self._stopping:
            raise RuntimeError("collector has already started")
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"https-mitm-{self._context.run_id if self._context else 'run'}",
        )
        self._server_thread.start()
        self._started = True

    def checkpoint(self, label: str) -> EvidenceCursor:
        if not self._started or self._closed:
            raise RuntimeError("collector is not running")
        with self._condition:
            value = _encode_cursor_state(
                self._sequence,
                self._error_count,
                self._dropped_error_count,
                self._resource_limit_counts,
            )
        return EvidenceCursor(self.name, value)

    def collect(self, window: ObservationWindow) -> CollectorResult:
        start, end = window.cursors_for(self.name)
        start_state = _decode_cursor_state(start.value)
        end_state = _decode_cursor_state(end.value)
        start_value, start_errors, start_dropped, start_limits = start_state
        end_value, end_errors, end_dropped, end_limits = end_state
        if (
            end_value < start_value
            or end_errors < start_errors
            or end_dropped < start_dropped
            or any(
                end_limits.get(name, 0) < count
                for name, count in start_limits.items()
            )
        ):
            raise ValueError("HTTPS MITM end cursor precedes start cursor")
        with self._condition:
            selected = tuple(
                dict(item)
                for item in self._observations
                if start_value < int(item["sequence"]) <= end_value
            )
            errors = tuple(
                error
                for sequence, error in self._errors
                if start_value < sequence <= end_value
            )
            resource_limits = tuple(
                sorted(
                    name
                    for name, count in end_limits.items()
                    if count > start_limits.get(name, 0)
                )
            )
            error_count = end_errors - start_errors
            dropped_errors = end_dropped - start_dropped
        return self._result(
            selected,
            errors,
            start.observed_at,
            end.observed_at,
            resource_limits=resource_limits,
            error_count=error_count,
            dropped_errors=dropped_errors,
        )

    def drain(self, timeout_seconds: float) -> CollectorResult:
        if not self._started or self._closed:
            raise RuntimeError("collector is not running")
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        deadline = time.monotonic() + timeout_seconds
        with self._condition:
            while self._active_exchanges:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    health = CollectorHealth(
                        CollectorHealthState.UNHEALTHY,
                        "HTTPS exchanges did not drain before timeout",
                        self._active_exchanges,
                    )
                    return CollectorResult(
                        self.name,
                        CollectorStatus.TIMEOUT,
                        health,
                        tuple(dict(item) for item in self._observations),
                        limitations=("One or more HTTPS responses were incomplete.",),
                    )
                self._condition.wait(remaining)
            observations = tuple(dict(item) for item in self._observations)
            errors = tuple(error for _, error in self._errors)
            resource_limits = tuple(sorted(self._resource_limit_counts))
            error_count = self._error_count
            dropped_errors = self._dropped_error_count
        now = utc_now()
        return self._result(
            observations,
            errors,
            now,
            now,
            resource_limits=resource_limits,
            error_count=error_count,
            dropped_errors=dropped_errors,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._stopping = True
        errors: list[BaseException] = []
        server = self._server
        if server is not None:
            if self._started and not self._server_shutdown:
                try:
                    server.shutdown()
                    self._server_shutdown = True
                except BaseException as error:
                    errors.append(error)
            with self._condition:
                sockets = tuple(self._open_sockets)
            for active_socket in sockets:
                try:
                    active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    active_socket.close()
                except OSError:
                    pass
            try:
                server.server_close()
            except BaseException as error:
                errors.append(error)
        if self._server_thread is not None:
            self._server_thread.join(timeout=max(2.0, self._socket_timeout + 1.0))
            if self._server_thread.is_alive():
                errors.append(RuntimeError("HTTPS MITM server thread did not stop"))
        if not errors and self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("HTTPS MITM collector cleanup failed", errors)
        self._ca_key = None
        self._ca_cert = None
        self._certificate_contexts.clear()
        self._closed = True

    def _create_ca(self, directory: Path) -> None:
        now = datetime.now(timezone.utc)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "Agent Test Run-Scoped CA")]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=8))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(key, hashes.SHA256())
        )
        ca_path = directory / "ca.pem"
        ca_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        self._ca_key, self._ca_cert, self._ca_path = key, cert, ca_path

    def _merge_ca_bundle(self, directory: Path, existing_path: str | None) -> None:
        """Preserve the process's existing Node trust roots in one valid PEM file."""

        if not existing_path:
            return
        source = Path(existing_path).expanduser()
        try:
            if not source.is_file():
                raise ValueError("existing NODE_EXTRA_CA_CERTS must be a regular file")
            if source.stat().st_size > _CA_BUNDLE_LIMIT:
                raise ValueError("existing NODE_EXTRA_CA_CERTS exceeds the merge limit")
            existing = source.read_bytes()
        except OSError as exc:
            raise ValueError("existing NODE_EXTRA_CA_CERTS cannot be read") from exc
        if b"-----BEGIN CERTIFICATE-----" not in existing:
            raise ValueError("existing NODE_EXTRA_CA_CERTS is not a PEM certificate bundle")
        if self._ca_path is None:
            raise RuntimeError("collector CA is unavailable")
        run_ca = self._ca_path.read_bytes()
        combined = directory / "combined-ca.pem"
        combined.write_bytes(existing.rstrip() + b"\n" + run_ca)
        self._ca_path = combined

    def _server_context_for(self, host: str) -> ssl.SSLContext:
        with self._condition:
            while True:
                cached = self._certificate_contexts.get(host)
                if cached is not None:
                    return cached
                if host not in self._certificate_reservations:
                    if (
                        len(self._certificate_contexts)
                        + len(self._certificate_reservations)
                        >= self._max_certificate_cache
                    ):
                        self._record_resource_limit_locked("certificate_cache")
                        raise _ResourceLimitReached(
                            "certificate cache limit reached"
                        )
                    self._certificate_reservations.add(host)
                    break
                self._condition.wait()
        try:
            if self._temp_dir is None or self._ca_key is None or self._ca_cert is None:
                raise RuntimeError("collector CA is unavailable")
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            now = datetime.now(timezone.utc)
            subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host[:64])])
            builder = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(self._ca_cert.subject)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=1))
                .not_valid_after(now + timedelta(hours=4))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
                .add_extension(
                    x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False
                )
            )
            try:
                alternative_name: x509.GeneralName = x509.IPAddress(
                    ipaddress.ip_address(host)
                )
            except ValueError:
                alternative_name = x509.DNSName(host)
            cert = builder.add_extension(
                x509.SubjectAlternativeName([alternative_name]), False
            ).sign(self._ca_key, hashes.SHA256())
            identifier = uuid.uuid4().hex
            cert_path = Path(self._temp_dir.name) / f"leaf-{identifier}.pem"
            key_path = Path(self._temp_dir.name) / f"leaf-{identifier}.key"
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.set_alpn_protocols(["http/1.1"])
            context.load_cert_chain(cert_path, key_path)
            with self._condition:
                self._certificate_contexts[host] = context
            return context
        finally:
            with self._condition:
                self._certificate_reservations.discard(host)
                self._condition.notify_all()

    def _handle_client(self, raw_socket: socket.socket) -> None:
        raw_socket.settimeout(self._socket_timeout)
        reader = _BufferedSocket(raw_socket)
        connect_head = reader.read_until(b"\r\n\r\n", _HEADER_LIMIT)
        if not connect_head:
            return
        first_line = connect_head.split(b"\r\n", 1)[0].decode("latin1", "replace")
        parts = first_line.split(" ", 2)
        if len(parts) < 2 or parts[0].upper() != "CONNECT":
            raw_socket.sendall(
                b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n"
                b"Connection: close\r\n\r\n"
            )
            return
        host, port = _parse_authority(parts[1])
        if not host or port < 1 or port > 65535:
            raise ValueError("invalid CONNECT target")
        intercept = self._should_intercept(host)
        server_context = self._server_context_for(host) if intercept else None
        upstream_raw = self._connect_target(host, port)
        self._register_socket(upstream_raw)
        raw_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        if not intercept:
            try:
                if not self._reserve_exchange():
                    raise _ResourceLimitReached("exchange limit reached")
                self._relay_tunnel(raw_socket, reader, upstream_raw, host, port)
            finally:
                self._unregister_socket(upstream_raw)
                upstream_raw.close()
            return

        if reader.buffer:
            raise ValueError("client sent TLS data before CONNECT was acknowledged")
        assert server_context is not None
        client_tls: ssl.SSLSocket | None = None
        upstream_tls: ssl.SSLSocket | None = None
        try:
            client_tls = server_context.wrap_socket(raw_socket, server_side=True)
            self._register_socket(client_tls)
            upstream_context = self._upstream_ssl_context or ssl.create_default_context()
            upstream_context.set_alpn_protocols(["http/1.1"])
            upstream_tls = upstream_context.wrap_socket(upstream_raw, server_hostname=host)
            self._register_socket(upstream_tls)
            client_reader = _BufferedSocket(client_tls)
            upstream_reader = _BufferedSocket(upstream_tls)
            while not self._stopping:
                request_head = client_reader.read_until(b"\r\n\r\n", _HEADER_LIMIT)
                if not request_head:
                    break
                if not self._reserve_exchange():
                    client_tls.sendall(
                        b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n"
                        b"Connection: close\r\n\r\n"
                    )
                    raise _ResourceLimitReached("exchange limit reached")
                keep_open = self._forward_exchange(
                    host,
                    port,
                    client_tls,
                    client_reader,
                    upstream_tls,
                    upstream_reader,
                    request_head,
                )
                if not keep_open:
                    break
        finally:
            for active_socket in (upstream_tls, upstream_raw, client_tls):
                if active_socket is not None:
                    self._unregister_socket(active_socket)
                    try:
                        active_socket.close()
                    except OSError:
                        pass

    def _should_intercept(self, host: str) -> bool:
        return host.casefold().rstrip(".") in self._mitm_hosts

    def _connect_target(self, host: str, port: int) -> socket.socket:
        proxy = self._upstream_proxy
        bypass_upstream = any(
            _no_proxy_matches_target(entry, host, port)
            for entry in self._upstream_no_proxy
        )
        if proxy is None or bypass_upstream:
            return socket.create_connection((host, port), self._socket_timeout)
        connection = socket.create_connection(
            (proxy.host, proxy.port), self._socket_timeout
        )
        try:
            authority = _format_authority(host, port)
            lines = [
                f"CONNECT {authority} HTTP/1.1\r\n",
                f"Host: {authority}\r\n",
                "Proxy-Connection: keep-alive\r\n",
            ]
            if proxy.authorization is not None:
                lines.append(f"Proxy-Authorization: {proxy.authorization}\r\n")
            lines.append("\r\n")
            connection.sendall("".join(lines).encode("latin1"))
            response = _BufferedSocket(connection).read_until(
                b"\r\n\r\n", _HEADER_LIMIT
            )
            first_line = response.split(b"\r\n", 1)[0].decode("latin1", "replace")
            parts = first_line.split(" ", 2)
            if (
                len(parts) < 2
                or not parts[0].startswith("HTTP/1.")
                or not parts[1].isdigit()
                or not 200 <= int(parts[1]) < 300
            ):
                status = parts[1] if len(parts) >= 2 else "invalid"
                raise ConnectionError(
                    f"upstream proxy CONNECT failed with HTTP {status}"
                )
            return connection
        except BaseException:
            connection.close()
            raise

    def _relay_tunnel(
        self,
        client: socket.socket,
        client_reader: _BufferedSocket,
        upstream: socket.socket,
        host: str,
        port: int,
    ) -> None:
        started_at = _iso_now()
        error: str | None = None
        with self._condition:
            self._active_exchanges += 1
        try:
            if client_reader.buffer:
                upstream.sendall(client_reader.read_some(len(client_reader.buffer)))
            while not self._stopping:
                readable, _, _ = select.select(
                    (client, upstream), (), (), min(1.0, self._socket_timeout)
                )
                if not readable:
                    continue
                for source in readable:
                    data = source.recv(_IO_CHUNK_SIZE)
                    if not data:
                        return
                    (upstream if source is client else client).sendall(data)
        except Exception as exc:
            if not self._stopping:
                error = f"{type(exc).__name__}: {str(exc)[:240]}"
                self._record_collector_error(type(exc).__name__)
        finally:
            observation = {
                "exchange_id": uuid.uuid4().hex,
                "sequence": 0,
                "started_at": started_at,
                "completed_at": _iso_now(),
                "scheme": "connect",
                "host": host,
                "port": port,
                "method": "CONNECT",
                "path": _format_authority(host, port),
                "request_headers": {},
                "request_body": "",
                "response_status": 200,
                "response_headers": {},
                "response_body": "",
                "request_complete": error is None,
                "response_complete": error is None,
                "error": error,
                "request_body_bytes": 0,
                "response_body_bytes": 0,
                "request_wire_bytes": 0,
                "response_wire_bytes": 0,
                "request_body_truncated": False,
                "response_body_truncated": False,
                "intercepted": False,
            }
            with self._condition:
                self._sequence += 1
                observation["sequence"] = self._sequence
                self._observations.append(observation)
                self._active_exchanges -= 1
                self._condition.notify_all()

    def _forward_exchange(
        self,
        host: str,
        port: int,
        client: ssl.SSLSocket,
        client_reader: _BufferedSocket,
        upstream: ssl.SSLSocket,
        upstream_reader: _BufferedSocket,
        request_head: bytes,
    ) -> bool:
        exchange_id = uuid.uuid4().hex
        started_at = _iso_now()
        with self._condition:
            self._active_exchanges += 1
        request_capture = _CaptureBuffer(self._max_body_bytes)
        response_capture = _CaptureBuffer(self._max_body_bytes)
        request_complete = False
        response_complete = False
        response_status: int | None = None
        response_headers: list[tuple[str, str]] = []
        error: str | None = None
        method = ""
        path = ""
        request_headers: list[tuple[str, str]] = []
        keep_open = False
        try:
            method, path, request_headers = self._parse_request_head(request_head)
            request_capture = _CaptureBuffer(
                self._max_body_bytes,
                _header_value(request_headers, "content-encoding"),
            )
            forwarded_head = self._serialize_request_head(
                method, path, request_headers, host
            )
            upstream.sendall(forwarded_head)
            request_complete = self._relay_body(
                client_reader,
                upstream,
                request_headers,
                request_capture,
            )
            if request_capture.wire_bytes:
                request_capture.finish()
            while True:
                response_head = upstream_reader.read_until(b"\r\n\r\n", _HEADER_LIMIT)
                if not response_head:
                    raise EOFError("upstream closed before response headers")
                response_status, response_headers = self._parse_response_head(response_head)
                client.sendall(response_head)
                if response_status < 200 and response_status != 101:
                    continue
                break
            response_capture = _CaptureBuffer(
                self._max_body_bytes,
                _header_value(response_headers, "content-encoding"),
            )
            response_complete = self._relay_response_body(
                upstream_reader,
                client,
                response_headers,
                response_capture,
                method,
                response_status,
            )
            if response_capture.wire_bytes:
                response_capture.finish()
            decoding_errors = tuple(
                value
                for value in (
                    request_capture.decode_error,
                    response_capture.decode_error,
                )
                if value is not None
            )
            if decoding_errors:
                error = "; ".join(decoding_errors)
                self._record_collector_error("BodyDecodeError")
            request_connection = _connection_directive(request_headers)
            response_connection = _connection_directive(response_headers)
            keep_open = (
                request_connection != "close"
                and response_connection != "close"
                and response_status != 101
                and _has_explicit_body_framing(response_headers, method, response_status)
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:240]}"
            self._record_collector_error(type(exc).__name__)
        finally:
            completed_at = _iso_now()
            observation = self._observation(
                exchange_id=exchange_id,
                started_at=started_at,
                completed_at=completed_at,
                host=host,
                port=port,
                method=method,
                path=path,
                request_headers=request_headers,
                request_capture=request_capture,
                response_status=response_status,
                response_headers=response_headers,
                response_capture=response_capture,
                request_complete=request_complete,
                response_complete=response_complete,
                error=error,
            )
            with self._condition:
                self._sequence += 1
                observation["sequence"] = self._sequence
                self._observations.append(observation)
                self._active_exchanges -= 1
                self._condition.notify_all()
        return keep_open

    @staticmethod
    def _parse_request_head(head: bytes) -> tuple[str, str, list[tuple[str, str]]]:
        lines = head[:-4].split(b"\r\n")
        parts = lines[0].decode("latin1", "replace").split(" ", 2)
        if len(parts) != 3 or not parts[2].startswith("HTTP/1."):
            raise ValueError("unsupported HTTP request line")
        return parts[0], parts[1], _parse_headers(lines[1:])

    @staticmethod
    def _parse_response_head(head: bytes) -> tuple[int, list[tuple[str, str]]]:
        lines = head[:-4].split(b"\r\n")
        parts = lines[0].decode("latin1", "replace").split(" ", 2)
        if len(parts) < 2 or not parts[0].startswith("HTTP/1."):
            raise ValueError("unsupported HTTP response line")
        return int(parts[1]), _parse_headers(lines[1:])

    @staticmethod
    def _serialize_request_head(
        method: str, path: str, headers: list[tuple[str, str]], host: str
    ) -> bytes:
        lines = [f"{method} {path} HTTP/1.1\r\n"]
        has_host = False
        for name, value in headers:
            lowered = name.lower()
            if lowered == "proxy-connection":
                continue
            if lowered == "expect":
                # The proxy already owns request framing; forwarding 100-continue
                # would otherwise require a second interleaved response loop.
                continue
            has_host = has_host or lowered == "host"
            lines.append(f"{name}: {value}\r\n")
        if not has_host:
            lines.append(f"Host: {host}\r\n")
        lines.append("\r\n")
        return "".join(lines).encode("latin1")

    def _relay_body(
        self,
        source: _BufferedSocket,
        destination: socket.socket,
        headers: list[tuple[str, str]],
        capture: _CaptureBuffer,
    ) -> bool:
        transfer_encoding = _header_value(headers, "transfer-encoding").lower()
        if "chunked" in transfer_encoding:
            return self._relay_chunked(source, destination, capture)
        content_length = _content_length(headers)
        if content_length is None or content_length == 0:
            return True
        remaining = content_length
        while remaining:
            data = source.read_exact(min(_IO_CHUNK_SIZE, remaining))
            destination.sendall(data)
            capture.append(data)
            remaining -= len(data)
        return True

    def _relay_response_body(
        self,
        source: _BufferedSocket,
        destination: socket.socket,
        headers: list[tuple[str, str]],
        capture: _CaptureBuffer,
        method: str,
        status: int,
    ) -> bool:
        if method.upper() == "HEAD" or 100 <= status < 200 or status in (204, 304):
            return True
        transfer_encoding = _header_value(headers, "transfer-encoding").lower()
        if "chunked" in transfer_encoding:
            return self._relay_chunked(source, destination, capture)
        content_length = _content_length(headers)
        if content_length is not None:
            remaining = content_length
            while remaining:
                data = source.read_exact(min(_IO_CHUNK_SIZE, remaining))
                destination.sendall(data)
                capture.append(data)
                remaining -= len(data)
            return True
        while True:
            data = source.read_some()
            if not data:
                return True
            destination.sendall(data)
            capture.append(data)

    @staticmethod
    def _relay_chunked(
        source: _BufferedSocket,
        destination: socket.socket,
        capture: _CaptureBuffer,
    ) -> bool:
        while True:
            size_line = source.read_until(b"\r\n", _HEADER_LIMIT)
            destination.sendall(size_line)
            raw_size = size_line[:-2].split(b";", 1)[0].strip()
            try:
                size = int(raw_size, 16)
            except ValueError as exc:
                raise ValueError("invalid HTTP chunk size") from exc
            if size == 0:
                while True:
                    trailer = source.read_until(b"\r\n", _HEADER_LIMIT)
                    destination.sendall(trailer)
                    if trailer == b"\r\n":
                        return True
            data = source.read_exact(size)
            terminator = source.read_exact(2)
            if terminator != b"\r\n":
                raise ValueError("invalid HTTP chunk terminator")
            destination.sendall(data + terminator)
            capture.append(data)

    def _observation(
        self,
        *,
        exchange_id: str,
        started_at: str,
        completed_at: str,
        host: str,
        port: int,
        method: str,
        path: str,
        request_headers: list[tuple[str, str]],
        request_capture: _CaptureBuffer,
        response_status: int | None,
        response_headers: list[tuple[str, str]],
        response_capture: _CaptureBuffer,
        request_complete: bool,
        response_complete: bool,
        error: str | None,
    ) -> dict[str, Any]:
        return {
            "exchange_id": exchange_id,
            "sequence": 0,
            "started_at": started_at,
            "completed_at": completed_at,
            "scheme": "https",
            "host": host,
            "port": port,
            "method": method,
            "path": self._redact_path(path),
            "request_headers": self._redact_headers(request_headers),
            "request_body": self._redact_text(
                _decode_capture(request_capture.data, request_headers)
            ),
            "response_status": response_status,
            "response_headers": self._redact_headers(response_headers),
            "response_body": self._redact_text(
                _decode_capture(response_capture.data, response_headers)
            ),
            "request_complete": request_complete,
            "response_complete": response_complete,
            "error": error,
            "request_body_bytes": request_capture.total_bytes,
            "response_body_bytes": response_capture.total_bytes,
            "request_wire_bytes": request_capture.wire_bytes,
            "response_wire_bytes": response_capture.wire_bytes,
            "request_body_truncated": request_capture.truncated,
            "response_body_truncated": response_capture.truncated,
            "intercepted": True,
        }

    def _redact_headers(self, headers: list[tuple[str, str]]) -> dict[str, str]:
        redacted: list[tuple[str, str]] = []
        for name, value in headers:
            if _is_sensitive_name(name):
                value = "<redacted>"
            else:
                value = self._redact_text(value)
            redacted.append((name.lower(), value))
        return _header_map(redacted)

    def _redact_path(self, path: str) -> str:
        parts = urlsplit(path)
        if not parts.query:
            return self._redact_text(path)
        query = urlencode(
            [
                (
                    name,
                    "<redacted>"
                    if _is_sensitive_name(name)
                    else self._redact_text(value),
                )
                for name, value in parse_qsl(parts.query, keep_blank_values=True)
            ]
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    def _redact_text(self, value: str) -> str:
        context = self._context
        for secret in context.secrets if context is not None else ():
            value = value.replace(secret, "<redacted>")
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError, RecursionError):
            value, parsed_stream_item = self._redact_stream_json(value)
            if not parsed_stream_item:
                value = self._redact_unstructured_text(value)
            return value
        return json.dumps(
            self._redact_json(parsed),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def _redact_stream_json(self, value: str) -> tuple[str, bool]:
        output: list[str] = []
        event_lines: list[str] = []
        found_stream_item = False
        for line in value.splitlines(keepends=True):
            content = line.rstrip("\r\n")
            if content:
                event_lines.append(line)
                continue
            redacted_event, event_has_data = self._redact_sse_event(event_lines)
            output.append(redacted_event)
            output.append(line)
            found_stream_item = found_stream_item or event_has_data
            event_lines = []
        if event_lines:
            redacted_event, event_has_data = self._redact_sse_event(event_lines)
            output.append(redacted_event)
            found_stream_item = found_stream_item or event_has_data
        return "".join(output), found_stream_item

    def _redact_sse_event(self, lines: list[str]) -> tuple[str, bool]:
        matches: list[tuple[int, re.Match[str], str]] = []
        for index, line in enumerate(lines):
            content = line.rstrip("\r\n")
            ending = line[len(content) :]
            match = re.match(r"^(\s*data:\s?)(.*)$", content)
            if match is not None:
                matches.append((index, match, ending))
        if not matches:
            return (
                "".join(
                    self._redact_unstructured_text(line.rstrip("\r\n"))
                    + line[len(line.rstrip("\r\n")) :]
                    for line in lines
                ),
                False,
            )

        payload = "\n".join(match.group(2) for _, match, _ in matches)
        if payload.strip() == "[DONE]":
            redacted_payload = payload
        else:
            try:
                parsed = json.loads(payload)
            except (json.JSONDecodeError, ValueError, RecursionError):
                redacted_payload = self._redact_unstructured_text(payload)
            else:
                redacted_payload = json.dumps(
                    self._redact_json(parsed),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

        first_index, first_match, _ = matches[0]
        data_indexes = {index for index, _, _ in matches}
        newline = (
            "\r\n" if any(ending == "\r\n" for _, _, ending in matches) else "\n"
        )
        final_ending = matches[-1][2]
        if not final_ending and any(
            index > first_index and index not in data_indexes
            for index in range(len(lines))
        ):
            final_ending = newline
        rebuilt_data = newline.join(
            f"{first_match.group(1)}{part}" for part in redacted_payload.split("\n")
        ) + final_ending
        output: list[str] = []
        for index, line in enumerate(lines):
            if index == first_index:
                output.append(rebuilt_data)
            elif index not in data_indexes:
                content = line.rstrip("\r\n")
                output.append(
                    self._redact_unstructured_text(content) + line[len(content) :]
                )
        return "".join(output), True

    @staticmethod
    def _redact_unstructured_text(value: str) -> str:
        def redact_json_assignment(match: re.Match[str]) -> str:
            try:
                key = json.loads(match.group("key"))
            except (json.JSONDecodeError, ValueError):
                key = match.group("key").strip('"')
            if _is_sensitive_name(str(key)):
                return f'{match.group("prefix")}"<redacted>"'
            return match.group(0)

        value = _JSON_FIELD_ASSIGNMENT.sub(redact_json_assignment, value)
        value = _TEXT_SECRET_ASSIGNMENT.sub(r"\1\2<redacted>", value)
        return _BEARER_CREDENTIAL.sub(r"\1 <redacted>", value)

    def _redact_json(self, value: Any, *, depth: int = 0) -> Any:
        if depth > 32:
            return "<redacted>"
        if isinstance(value, dict):
            return {
                str(key): (
                    "<redacted>"
                    if _is_sensitive_name(str(key))
                    else self._redact_json(item, depth=depth + 1)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact_json(item, depth=depth + 1) for item in value]
        if isinstance(value, str):
            context = self._context
            for secret in context.secrets if context is not None else ():
                value = value.replace(secret, "<redacted>")
            return _BEARER_CREDENTIAL.sub(r"\1 <redacted>", value)
        return value

    def _result(
        self,
        observations: tuple[dict[str, Any], ...],
        errors: tuple[str, ...],
        started_at: datetime,
        ended_at: datetime,
        *,
        resource_limits: tuple[str, ...],
        error_count: int,
        dropped_errors: int,
    ) -> CollectorResult:
        incomplete = any(
            not item["request_complete"] or not item["response_complete"]
            for item in observations
        )
        truncated = tuple(
            item
            for item in observations
            if item["request_body_truncated"] or item["response_body_truncated"]
        )
        if errors or incomplete:
            health = CollectorHealth(
                CollectorHealthState.UNHEALTHY,
                "One or more HTTPS exchanges were incomplete",
                error_count + sum(1 for item in observations if item["error"]),
            )
            status = CollectorStatus.ERROR
            limitations = (
                "Incomplete HTTPS exchanges cannot support absence claims.",
                *(
                    (f"{dropped_errors} error diagnostics exceeded the retention limit.",)
                    if dropped_errors
                    else ()
                ),
            )
        elif resource_limits:
            health = CollectorHealth(
                CollectorHealthState.DEGRADED,
                "Run-scoped collector limit reached: " + ", ".join(resource_limits),
                len(resource_limits) + dropped_errors,
            )
            status = CollectorStatus.UNVERIFIED
            limitations = (
                "Collector resource limits prevent completeness and absence claims.",
            )
        elif truncated:
            health = CollectorHealth(
                CollectorHealthState.DEGRADED,
                "One or more HTTPS payloads were truncated",
                len(truncated),
            )
            status = CollectorStatus.UNVERIFIED
            limitations = (
                "Truncated HTTPS payloads cannot support completeness or absence claims.",
            )
        else:
            health = CollectorHealth()
            status = CollectorStatus.AVAILABLE if observations else CollectorStatus.MISSING
            limitations = (
                "Only traffic inherited through the configured HTTPS proxy is observed.",
                "Captured application payloads do not prove server-side persistence.",
            )
        return CollectorResult(
            self.name,
            status,
            health,
            observations,
            started_at,
            ended_at,
            limitations,
            diagnostics={
                "retained_error_types": list(errors),
                "unattributed_error_count": max(
                    0,
                    len(errors)
                    - sum(1 for item in observations if item.get("error")),
                ),
                "dropped_error_count": dropped_errors,
                "resource_limits": list(resource_limits),
            },
        )

    def _register_socket(self, active_socket: socket.socket) -> None:
        with self._condition:
            self._open_sockets.add(active_socket)

    def _unregister_socket(self, active_socket: socket.socket) -> None:
        with self._condition:
            self._open_sockets.discard(active_socket)

    def _record_collector_error(self, error: str) -> None:
        with self._condition:
            self._sequence += 1
            self._error_count += 1
            if len(self._errors) < self._max_error_records:
                self._errors.append((self._sequence, error))
            else:
                self._dropped_error_count += 1
                self._record_resource_limit_locked("error_records")
            self._condition.notify_all()

    def _reserve_connection(self) -> bool:
        with self._condition:
            if self._active_connections >= self._max_connections:
                self._record_resource_limit_locked("connections")
                return False
            self._connection_count += 1
            self._active_connections += 1
            return True

    def _release_connection(self) -> None:
        with self._condition:
            if self._active_connections > 0:
                self._active_connections -= 1
            self._condition.notify_all()

    def _reserve_exchange(self) -> bool:
        with self._condition:
            if self._exchange_count >= self._max_exchanges:
                self._record_resource_limit_locked("exchanges")
                return False
            self._exchange_count += 1
            return True

    def _record_resource_limit_locked(self, resource: str) -> None:
        self._resource_limit_counts[resource] = (
            self._resource_limit_counts.get(resource, 0) + 1
        )
        self._condition.notify_all()


def _parse_headers(lines: Iterable[bytes]) -> list[tuple[str, str]]:
    headers: list[tuple[str, str]] = []
    for line in lines:
        if not line:
            continue
        if b":" not in line:
            raise ValueError("malformed HTTP header")
        name, value = line.split(b":", 1)
        headers.append(
            (name.decode("latin1", "replace"), value.strip().decode("latin1", "replace"))
        )
    return headers


def _header_value(headers: Iterable[tuple[str, str]], name: str) -> str:
    values = [value for key, value in headers if key.lower() == name.lower()]
    return ", ".join(values)


def _content_length(headers: Iterable[tuple[str, str]]) -> int | None:
    value = _header_value(headers, "content-length")
    if not value:
        return None
    length = int(value)
    if length < 0:
        raise ValueError("negative Content-Length")
    return length


def _connection_directive(headers: Iterable[tuple[str, str]]) -> str:
    return _header_value(headers, "connection").lower()


def _has_explicit_body_framing(
    headers: Iterable[tuple[str, str]], method: str, status: int
) -> bool:
    return (
        method.upper() == "HEAD"
        or 100 <= status < 200
        or status in (204, 304)
        or _content_length(headers) is not None
        or "chunked" in _header_value(headers, "transfer-encoding").lower()
    )


def _decode_capture(
    data: bytes | bytearray,
    headers: Iterable[tuple[str, str]],
) -> str:
    raw = bytes(data)
    content_type = _header_value(headers, "content-type")
    charset_match = re.search(r"charset=([^;\s]+)", content_type, re.IGNORECASE)
    charset = charset_match.group(1).strip('"\'') if charset_match else "utf-8"
    try:
        return raw.decode(charset, "replace")
    except LookupError:
        return raw.decode("utf-8", "replace")


__all__ = ["HttpsMitmCollector"]
