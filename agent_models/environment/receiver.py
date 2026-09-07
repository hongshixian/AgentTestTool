"""Loopback-only tool receiver owned by the evaluator, outside the Agent process."""

from __future__ import annotations

import http.client
import json
import math
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator, Protocol


class ToolBackend(Protocol):
    def list_tools(self) -> list[dict[str, Any]]: ...
    def call(self, name: str, arguments: dict[str, Any], *, correlation_id: str,
             timeout: float) -> Any: ...
    def close(self) -> None: ...


class HttpToolReceiver:
    """Expose only simulated tool operations; this is not an MCP HTTP transport."""

    def __init__(self, runtime: ToolBackend, *, event_sink=None,
                 request_timeout: float = 10, max_body_bytes: int = 1_048_576,
                 max_connections: int = 32) -> None:
        if isinstance(request_timeout, bool) or not isinstance(request_timeout, (int, float)):
            raise ValueError("request_timeout must be a number")
        try:
            valid_timeout = math.isfinite(request_timeout) and request_timeout > 0
        except OverflowError:
            valid_timeout = False
        if not valid_timeout:
            raise ValueError("request_timeout must be finite and positive")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
               for value in (max_body_bytes, max_connections)):
            raise ValueError("receiver limits must be positive integers")
        self.runtime = runtime
        self.event_sink = event_sink
        self.request_timeout = request_timeout
        self.max_body_bytes = max_body_bytes
        self._prefix = "/" + uuid.uuid4().hex
        self._slots = threading.BoundedSemaphore(max_connections)
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._connections: set[socket.socket] = set()
        self._handlers: set[threading.Thread] = set()
        self._close_workers: list[threading.Thread] = []
        self._close_errors: list[str] = []
        self._errors: list[str] = []
        self._requests = 0
        self._active = 0
        self._active_operations = 0
        self._pause_depth = 0
        self._probed = False
        self._closed = False
        owner = self

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = False

            def process_request(self, request, client_address):
                if not owner._slots.acquire(blocking=False):
                    owner._fail("connection capacity exceeded")
                    self.shutdown_request(request)
                    return
                worker = None
                try:
                    with owner._condition:
                        if owner._closed:
                            self.shutdown_request(request)
                            owner._slots.release()
                            return
                        owner._connections.add(request)
                        worker = threading.Thread(target=self.process_request_thread,
                                                  args=(request, client_address), daemon=True)
                        owner._handlers.add(worker)
                        worker.start()
                        owner._condition.notify_all()
                except BaseException:
                    with owner._condition:
                        owner._connections.discard(request)
                        if worker is not None:
                            owner._handlers.discard(worker)
                        owner._condition.notify_all()
                    owner._slots.release()
                    raise

            def process_request_thread(self, request, client_address):
                current = threading.current_thread()
                try:
                    super().process_request_thread(request, client_address)
                finally:
                    with owner._condition:
                        owner._connections.discard(request)
                        owner._handlers.discard(current)
                        owner._condition.notify_all()
                    owner._slots.release()

            def handle_error(self, request, client_address):
                if not owner._closed:
                    owner._fail("receiver handler failed")

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def setup(self):
                super().setup()
                self.connection.settimeout(owner.request_timeout)

            def log_message(self, format, *args):
                # Never send caller-provided headers, URLs or credentials to stderr.
                return

            def log_error(self, format, *args):
                if not owner._closed:
                    owner._emit("http_protocol_rejected", {"reason": "invalid or timed out HTTP request"})

            def do_GET(self):
                self._dispatch()

            def do_POST(self):
                self._dispatch()

            def _reply(self, status: int, data: dict[str, Any]):
                encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
                if len(encoded) > owner.max_body_bytes:
                    owner._fail("response exceeds configured byte limit")
                    status, encoded = 500, b'{"error":"response limit exceeded"}'
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(encoded)

            def _dispatch(self):
                with owner._lock:
                    owner._active += 1
                correlation = uuid.uuid4().hex
                admitted = False
                try:
                    # No browser access, redirects, external bind or DNS host aliases.
                    if self.headers.get("Origin") is not None or self.headers.get_all("Host") != [owner.authority]:
                        self._reply(403, {"error": "host or origin rejected"})
                        return
                    if owner._closed:
                        self._reply(503, {"error": "receiver closed"})
                        return
                    if not self.path.startswith(owner._prefix + "/"):
                        self._reply(404, {"error": "unknown endpoint"})
                        return
                    route = self.path[len(owner._prefix):]
                    if self.command == "GET" and route == "/health":
                        self._reply(200, {"healthy": not owner._errors})
                        return
                    with owner._condition:
                        unavailable = owner._closed or owner._pause_depth > 0
                        if not unavailable:
                            owner._active_operations += 1
                            admitted = True
                    if unavailable:
                        self._reply(503, {"error": "receiver paused or closed"})
                        return
                    owner._emit("http_received", {"method": self.command, "route": route}, correlation)
                    with owner._lock:
                        owner._requests += 1
                    if self.command == "GET" and route == "/tools":
                        self._reply(200, {"tools": owner.runtime.list_tools()})
                        return
                    if self.command != "POST" or route != "/call":
                        self._reply(404, {"error": "unknown operation"})
                        return
                    lengths = self.headers.get_all("Content-Length", [])
                    if self.headers.get("Transfer-Encoding") or len(lengths) != 1:
                        self._reply(400, {"error": "one Content-Length required"})
                        return
                    try:
                        if not lengths[0].isascii() or not lengths[0].isdigit():
                            raise ValueError("invalid length")
                        length = int(lengths[0])
                    except ValueError:
                        self._reply(400, {"error": "invalid Content-Length"})
                        return
                    if not 0 <= length <= owner.max_body_bytes:
                        self._reply(413, {"error": "request limit exceeded"})
                        return
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise ValueError("incomplete request")
                    payload = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
                    if not isinstance(payload, dict) or not isinstance(payload.get("name"), str):
                        raise ValueError("tool name required")
                    arguments = payload.get("arguments", {})
                    if not isinstance(arguments, dict):
                        raise ValueError("arguments must be an object")
                    result = owner.runtime.call(payload["name"], arguments,
                                                correlation_id=correlation,
                                                timeout=owner.request_timeout)
                    self._reply(200, {"body": result.body, "content_type": result.content_type,
                                      "is_error": result.is_error, "correlation_id": correlation})
                    owner._emit("http_responded", {"name": payload["name"]}, correlation)
                except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                    owner._emit("http_rejected", {"reason": "invalid tool request"}, correlation)
                    self._reply(400, {"error": "invalid tool request"})
                except TimeoutError:
                    owner._emit("http_timeout", {}, correlation)
                    self._reply(504, {"error": "tool request timed out"})
                except (BrokenPipeError, ConnectionResetError, OSError):
                    if not owner._closed:
                        owner._fail("connection failed before response completed")
                except Exception:
                    owner._fail("tool receiver failed")
                    self._reply(500, {"error": "tool receiver failed"})
                finally:
                    with owner._condition:
                        owner._active -= 1
                        if admitted:
                            owner._active_operations -= 1
                        owner._condition.notify_all()

        self._server = Server(("127.0.0.1", 0), Handler)
        self.authority = f"127.0.0.1:{self._server.server_port}"
        self.url = f"http://{self.authority}{self._prefix}"
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={"poll_interval": 0.05}, daemon=True)
        self._thread.start()
        try:
            self.probe()
        except BaseException as original:
            try:
                self.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup("Receiver startup and cleanup both failed", [original, cleanup])
            raise

    def _emit(self, kind: str, data: dict[str, Any], correlation: str | None = None) -> None:
        if self.event_sink is not None:
            try:
                self.event_sink("http_receiver", kind, data, correlation_id=correlation)
            except Exception:
                self._fail("evidence recording failed")
                raise

    def _fail(self, message: str) -> None:
        with self._lock:
            self._errors.append(message)

    def probe(self) -> None:
        """Check the actual listening socket; a probe is not a successful tool baseline."""
        conn = http.client.HTTPConnection("127.0.0.1", self._server.server_port,
                                          timeout=self.request_timeout)
        try:
            conn.request("GET", self._prefix + "/health")
            response = conn.getresponse()
            if response.status != 200 or json.loads(response.read()) != {"healthy": True}:
                raise RuntimeError("receiver health probe failed")
            self._emit("health_probe", {"healthy": True})
            self._probed = True
        finally:
            conn.close()

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {"healthy": self._probed and not self._errors and not self._closed
                    and self._thread.is_alive(), "errors": list(self._errors),
                    "requests": self._requests, "active_requests": self._active,
                    "active_connections": len(self._connections),
                    "active_operations": self._active_operations,
                    "paused": self._pause_depth > 0, "closed": self._closed}

    @contextmanager
    def paused(self) -> Iterator[HttpToolReceiver]:
        """Reject new tool requests and wait for admitted operations to finish.

        Health probes remain available, including while callers restore a stopped
        Agent's environment. Direct calls to the backend require caller coordination.
        """
        deadline = time.monotonic() + self.request_timeout
        with self._condition:
            if self._closed:
                raise RuntimeError("receiver is closed")
            self._pause_depth += 1
            self._condition.notify_all()
        try:
            with self._condition:
                while self._active_operations:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("receiver operations did not quiesce before pause")
                    self._condition.wait(remaining)
                if self._closed:
                    raise RuntimeError("receiver closed while pausing")
            yield self
        finally:
            with self._condition:
                self._pause_depth -= 1
                self._condition.notify_all()

    def close(self) -> None:
        """Boundedly stop listener, slow clients, tool waits and every handler.

        A backend that ignores close cannot be forcibly killed inside Python;
        timeout is explicit and a later close retries the quiescence check.
        """
        deadline = time.monotonic() + self.request_timeout

        def stop(operation, label):
            try:
                operation()
            except BaseException:
                with self._condition:
                    self._close_errors.append(label + " failed")
                    self._errors.append(label + " failed")
            finally:
                with self._condition:
                    self._condition.notify_all()

        with self._condition:
            if not self._closed:
                self._closed = True
                # Run independently: a misbehaving backend must not prevent the
                # listener and idle header/body readers from being stopped.
                for operation, label in ((self.runtime.close, "runtime close"),
                                         (self._server.shutdown, "listener shutdown")):
                    worker = threading.Thread(target=stop, args=(operation, label), daemon=True)
                    self._close_workers.append(worker)
                    worker.start()
                self._condition.notify_all()
            connections = tuple(self._connections)
            handlers = tuple(self._handlers)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self._server.server_close()
        # Joining threads (rather than only counting active dispatches) also covers
        # accepted connections still parsing headers and close-worker exceptions.
        for worker in [self._thread, *self._close_workers, *handlers]:
            worker.join(timeout=max(0, deadline - time.monotonic()))
        with self._condition:
            while self._connections or self._handlers:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
            if self._connections or self._handlers or any(
                    worker.is_alive() for worker in [self._thread, *self._close_workers, *handlers]):
                raise RuntimeError("receiver did not stop all connections, handlers, and backend work before timeout")
            if self._close_errors:
                raise RuntimeError("; ".join(self._close_errors))

    def __enter__(self) -> HttpToolReceiver:
        return self

    def __exit__(self, *_args) -> None:
        self.close()
