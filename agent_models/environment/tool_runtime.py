"""Thread-safe scripted tools with bounded waits and observable simulated effects.

The JSON-schema subset is type (one of object/array/string/integer/number/boolean/
null), properties, required, additionalProperties (boolean), items, enum, const,
minimum, maximum, minLength, maxLength, minItems, maxItems, title and description.
Unknown keywords are rejected, not silently treated as supported JSON Schema.
Calls consume their tool's response slot on receipt, including invalid calls.
Concurrent slot assignment follows lock acquisition order; completion order may
differ. Gates can make that completion ordering explicit. No external I/O occurs
except the supplied event sink, which must be synchronous and nonblocking.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable

from agent_models.evidence import JsonValue
from agent_models.tools import ToolDefinition, ToolEffect, ToolResponse, ToolSuite

EventSink = Callable[..., object]
MAX_JSON_BYTES = 1_048_576
MAX_WAIT_SECONDS = 300.0
SCHEMA_KEYS = frozenset({
    "type", "properties", "required", "additionalProperties", "items", "enum",
    "const", "minimum", "maximum", "minLength", "maxLength", "minItems",
    "maxItems", "title", "description",
})


class ToolRuntimeError(RuntimeError):
    """A tool could not complete within the configured runtime contract."""


class ToolValidationError(ToolRuntimeError, ValueError):
    pass


class ToolExhaustedError(ToolRuntimeError):
    pass


class ToolTimeoutError(ToolRuntimeError, TimeoutError):
    pass


class RuntimeClosedError(ToolRuntimeError):
    pass


class RuntimeHealthError(ToolRuntimeError):
    pass


def _json_copy(value: object) -> JsonValue:
    def check(item: object, depth: int = 0) -> None:
        if depth > 32:
            raise ToolValidationError("JSON nesting exceeds 32 levels")
        if type(item) is dict:
            if not all(type(k) is str for k in item):
                raise ToolValidationError("JSON object keys must be strings")
            for child in item.values():
                check(child, depth + 1)
        elif type(item) is list:
            for child in item:
                check(child, depth + 1)
        elif type(item) not in (str, int, float, bool, type(None)):
            raise ToolValidationError("Value is not JSON-compatible")
    check(value)
    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=True)
    except (ValueError, OverflowError, RecursionError) as exc:
        raise ToolValidationError("Invalid JSON value") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise ToolValidationError("JSON value exceeds size limit")
    return json.loads(encoded)


def _seconds(value: float, name: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ToolValidationError(f"{name} must be finite")
    if value < 0 or (positive and value == 0) or value > MAX_WAIT_SECONDS:
        raise ToolValidationError(f"{name} outside allowed time bounds")
    return float(value)


def _check_schema(schema: object, depth: int = 0) -> None:
    if type(schema) is not dict or depth > 32:
        raise ToolValidationError("Schema must be an object of bounded depth")
    if set(schema) - SCHEMA_KEYS:
        raise ToolValidationError("Unsupported JSON-schema keyword")
    kind = schema.get("type")
    if kind is not None and (not isinstance(kind, str) or kind not in {"object", "array", "string", "integer", "number", "boolean", "null"}):
        raise ToolValidationError("Unsupported schema type")
    groups = {"object": {"properties", "required", "additionalProperties"},
              "array": {"items", "minItems", "maxItems"},
              "string": {"minLength", "maxLength"},
              "number": {"minimum", "maximum"}}
    for expected, keys in groups.items():
        if keys & schema.keys() and kind not in ({"number", "integer"} if expected == "number" else {expected}):
            raise ToolValidationError("Typed schema constraints require matching type")
    for name in ("title", "description"):
        if name in schema and type(schema[name]) is not str:
            raise ToolValidationError("Schema annotations must be strings")
    if "properties" in schema:
        if type(schema["properties"]) is not dict:
            raise ToolValidationError("properties must be an object")
        for value in schema["properties"].values():
            _check_schema(value, depth + 1)
    if "required" in schema:
        required = schema["required"]
        if type(required) is not list or any(type(k) is not str for k in required) or len(set(required)) != len(required):
            raise ToolValidationError("required must contain unique field names")
    if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
        raise ToolValidationError("additionalProperties must be boolean")
    if "items" in schema:
        _check_schema(schema["items"], depth + 1)
    for lower, upper in (("minLength", "maxLength"), ("minItems", "maxItems"), ("minimum", "maximum")):
        for name in (lower, upper):
            if name in schema:
                value = schema[name]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ToolValidationError("Schema bounds must be finite numbers")
                if lower != "minimum" and (type(value) is not int or value < 0):
                    raise ToolValidationError("Size bounds must be nonnegative integers")
        if lower in schema and upper in schema and schema[lower] > schema[upper]:
            raise ToolValidationError("Schema bounds are inverted")
    if "enum" in schema and (type(schema["enum"]) is not list or not schema["enum"]):
        raise ToolValidationError("enum must be a nonempty JSON array")


def _equal(left: JsonValue, right: JsonValue) -> bool:
    # Python's True == 1 must not accept booleans as numeric enum values.
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _validate(value: JsonValue, schema: dict[str, JsonValue]) -> None:
    kind = schema.get("type")
    types = {"object": (dict,), "array": (list,), "string": (str,),
             "integer": (int,), "number": (int, float), "boolean": (bool,), "null": (type(None),)}
    if kind is not None and type(value) not in types[kind]:
        raise ToolValidationError("Arguments do not match schema type")
    if "const" in schema and not _equal(value, schema["const"]):
        raise ToolValidationError("Arguments do not match const")
    if "enum" in schema and not any(_equal(value, v) for v in schema["enum"]):
        raise ToolValidationError("Arguments do not match enum")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])):
            raise ToolValidationError("Required argument is missing")
        if schema.get("additionalProperties") is False and value.keys() - properties.keys():
            raise ToolValidationError("Unexpected argument")
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key])
    if isinstance(value, list) and "items" in schema:
        for item in value:
            _validate(item, schema["items"])
    bounds = (("minLength", "maxLength", len(value)),) if type(value) is str else ()
    if type(value) is list:
        bounds = (("minItems", "maxItems", len(value)),)
    if type(value) in (int, float):
        bounds = (("minimum", "maximum", value),)
    for lower, upper, measured in bounds:
        if (lower in schema and measured < schema[lower]) or (upper in schema and measured > schema[upper]):
            raise ToolValidationError("Argument outside schema bounds")


@dataclass(frozen=True, slots=True)
class ToolRuntimeSnapshot:
    suite_digest: str
    state: dict[str, JsonValue]
    call_counts: dict[str, int]
    released_gates: tuple[str, ...]


class ToolRuntime:
    """Scripted in-memory business runtime; snapshots never rewind evidence."""

    def __init__(self, suite: ToolSuite, *, initial_state: dict[str, JsonValue] | None = None,
                 event_sink: EventSink | None = None, default_timeout: float = 30,
                 max_delay_seconds: float = 60) -> None:
        self._condition = threading.Condition(threading.RLock())
        self._default_timeout = _seconds(default_timeout, "timeout", positive=True)
        self._max_delay = _seconds(max_delay_seconds, "maximum delay")
        self._suite = copy.deepcopy(suite)
        if suite.exhaustion not in {"repeat_last", "error"} or not suite.definitions:
            raise ToolValidationError("A nonempty suite and explicit exhaustion policy are required")
        self._tools: dict[str, ToolDefinition] = {}
        self._gates: dict[str, threading.Event] = {}
        for definition in self._suite.definitions:
            if not isinstance(definition.name, str) or not definition.name or definition.name in self._tools:
                raise ToolValidationError("Tool names must be nonempty and unique")
            if not isinstance(definition.description, str) or not definition.responses:
                raise ToolValidationError("Tool description and response sequence are required")
            _json_copy(definition.input_schema)
            _check_schema(definition.input_schema)
            for response in definition.responses:
                _json_copy(response.body)
                if not isinstance(response.content_type, str) or not response.content_type or type(response.is_error) is not bool:
                    raise ToolValidationError("Invalid response metadata")
                if _seconds(response.delay_seconds, "delay") > self._max_delay:
                    raise ToolValidationError("Response delay exceeds configured maximum")
                for gate in (response.gate, response.completion_gate):
                    if gate is not None:
                        if not isinstance(gate, str) or not gate:
                            raise ToolValidationError("Gate name must be nonempty")
                        self._gates.setdefault(gate, threading.Event())
                for effect in response.effects:
                    if effect.operation not in {"set", "append", "increment"} or not isinstance(effect.key, str) or not effect.key:
                        raise ToolValidationError("Invalid in-memory effect")
                    _json_copy(effect.value)
                    if effect.argument_path is not None:
                        if not isinstance(effect.argument_path, tuple) or any(type(p) not in (str, int) or (type(p) is int and p < 0) for p in effect.argument_path):
                            raise ToolValidationError("Invalid argument path")
                        if effect.value is not None:
                            raise ToolValidationError("Choose fixed value or argument path, not both")
            self._tools[definition.name] = definition
        self._suite_digest = hashlib.sha256(json.dumps(asdict(self._suite), sort_keys=True).encode()).hexdigest()
        state = _json_copy(initial_state if initial_state is not None else {})
        if not isinstance(state, dict):
            raise ToolValidationError("Initial state must be an object")
        self._state = state
        self._counts = dict.fromkeys(self._tools, 0)
        self._events: list[dict[str, JsonValue]] = []
        self._sink = event_sink
        self._inflight = 0
        self._closed = False
        self._healthy = True

    @property
    def healthy(self) -> bool:
        with self._condition:
            return self._healthy

    @property
    def state(self) -> dict[str, JsonValue]:
        with self._condition:
            return copy.deepcopy(self._state)

    @property
    def events(self) -> tuple[dict[str, JsonValue], ...]:
        with self._condition:
            return tuple(copy.deepcopy(self._events))

    def list_tools(self) -> list[dict[str, JsonValue]]:
        with self._condition:
            self._ensure_open()
            return [{"name": d.name, "description": d.description, "inputSchema": copy.deepcopy(d.input_schema)}
                    for d in self._tools.values()]

    def wait_for_call(self, name: str, *, count: int = 1,
                      timeout: float = 30) -> dict[str, JsonValue]:
        """Return the Nth received event for a tool, including invalid attempts.

        Count is relative to retained lifetime evidence, not restorable response
        slots. Receipt does not imply completion or authenticate the caller.
        Closed or unhealthy runtimes reject waits even when an event exists.
        """
        if not isinstance(name, str) or not name or name not in self._tools:
            raise ToolValidationError("Wait requires a configured tool name")
        if type(count) is not int or count < 1:
            raise ToolValidationError("Call count must be a positive integer")
        try:
            duration = _seconds(timeout, "wait timeout", positive=True)
        except OverflowError as exc:
            raise ToolValidationError("Wait timeout outside allowed time bounds") from exc
        deadline = time.monotonic() + duration
        cursor, received = 0, 0
        with self._condition:
            while True:
                self._ensure_open()
                while cursor < len(self._events):
                    event = self._events[cursor]
                    cursor += 1
                    if event["kind"] == "received" and event["data"].get("tool_name") == name:
                        received += 1
                        if received == count:
                            return copy.deepcopy(event)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ToolTimeoutError("No matching tool receipt before deadline")
                self._condition.wait(remaining)

    def wait_for_effect(
        self,
        name: str,
        *,
        key: str,
        count: int = 1,
        timeout: float = 30,
    ) -> dict[str, JsonValue]:
        """Return the Nth committed simulated effect for one tool and state key."""

        if not isinstance(name, str) or not name or name not in self._tools:
            raise ToolValidationError("Wait requires a configured tool name")
        if not isinstance(key, str) or not key:
            raise ToolValidationError("Effect wait requires a nonempty state key")
        if type(count) is not int or count < 1:
            raise ToolValidationError("Effect count must be a positive integer")
        try:
            duration = _seconds(timeout, "wait timeout", positive=True)
        except OverflowError as exc:
            raise ToolValidationError("Wait timeout outside allowed time bounds") from exc
        deadline = time.monotonic() + duration
        cursor, observed = 0, 0
        with self._condition:
            while True:
                self._ensure_open()
                while cursor < len(self._events):
                    event = self._events[cursor]
                    cursor += 1
                    if (
                        event["kind"] == "side_effect"
                        and event["data"].get("tool_name") == name
                        and event["data"].get("key") == key
                    ):
                        observed += 1
                        if observed == count:
                            return copy.deepcopy(event)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ToolTimeoutError("No matching tool effect before deadline")
                self._condition.wait(remaining)

    def _ensure_open(self) -> None:
        if not self._healthy:
            raise RuntimeHealthError("Tool evidence recording failed; runtime is closed")
        if self._closed:
            raise RuntimeClosedError("Tool runtime is closed")

    def _emit(self, kind: str, data: dict[str, JsonValue], correlation_id: str) -> None:
        event = {"source": "tool_runtime", "kind": kind, "data": copy.deepcopy(data),
                 "correlation_id": correlation_id, "sequence": len(self._events) + 1}
        self._events.append(event)
        if self._sink is not None:
            try:
                self._sink("tool_runtime", kind, copy.deepcopy(data), correlation_id=correlation_id)
            except Exception as exc:
                self._healthy = False
                self._closed = True
                self._condition.notify_all()
                raise RuntimeHealthError("Tool evidence sink failed; runtime closed") from exc
        self._condition.notify_all()

    def release_gate(self, name: str) -> None:
        with self._condition:
            self._ensure_open()
            if name not in self._gates:
                raise ToolValidationError("Unknown gate")
            self._gates[name].set()
            self._condition.notify_all()

    def reset_gate(self, name: str) -> None:
        with self._condition:
            self._ensure_open()
            if self._inflight:
                raise ToolRuntimeError("Cannot reset gates with calls in flight")
            if name not in self._gates:
                raise ToolValidationError("Unknown gate")
            self._gates[name].clear()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def snapshot(self) -> ToolRuntimeSnapshot:
        with self._condition:
            self._ensure_open()
            if self._inflight:
                raise ToolRuntimeError("Snapshot requires no calls in flight")
            return ToolRuntimeSnapshot(self._suite_digest, copy.deepcopy(self._state), dict(self._counts),
                                       tuple(k for k, event in self._gates.items() if event.is_set()))

    def restore(self, snapshot: ToolRuntimeSnapshot) -> None:
        with self._condition:
            self._ensure_open()
            if self._inflight:
                raise ToolRuntimeError("Restore requires no calls in flight")
            if snapshot.suite_digest != self._suite_digest or snapshot.call_counts.keys() != self._counts.keys():
                raise ToolValidationError("Snapshot belongs to a different tool suite")
            if any(type(v) is not int or v < 0 for v in snapshot.call_counts.values()):
                raise ToolValidationError("Invalid snapshot call counts")
            if not set(snapshot.released_gates) <= self._gates.keys():
                raise ToolValidationError("Snapshot has unknown gates")
            state = _json_copy(snapshot.state)
            if not isinstance(state, dict):
                raise ToolValidationError("Snapshot state must be an object")
            self._state = state
            self._counts = dict(snapshot.call_counts)
            for name, event in self._gates.items():
                event.set() if name in snapshot.released_gates else event.clear()

    def call(self, name: str, arguments: dict[str, JsonValue], *, correlation_id: str | None = None,
             timeout: float | None = None) -> ToolResponse:
        timeout = self._default_timeout if timeout is None else _seconds(timeout, "timeout", positive=True)
        if not isinstance(name, str) or (correlation_id is not None and (not isinstance(correlation_id, str) or not correlation_id)):
            raise ToolValidationError("Invalid tool name or correlation ID")
        deadline = time.monotonic() + timeout
        with self._condition:
            self._ensure_open()
            index = self._counts.get(name, 0) + 1
            if name in self._counts:
                self._counts[name] = index
            correlation_id = correlation_id or f"tool-call-{len(self._events) + 1}"
            data: dict[str, JsonValue] = {"tool_name": name, "call_index": index}
            self._inflight += 1
            try:
                try:
                    args = _json_copy(arguments)
                except ToolValidationError:
                    self._emit("received", data, correlation_id)
                    raise
                data["arguments"] = args
                self._emit("received", data, correlation_id)
                if not isinstance(args, dict):
                    raise ToolValidationError("Tool arguments must be an object")
                definition = self._tools.get(name)
                if definition is None:
                    raise ToolValidationError("Unknown tool")
                _validate(args, definition.input_schema)
                if index > len(definition.responses) and self._suite.exhaustion == "error":
                    raise ToolExhaustedError("Tool response sequence exhausted")
                response = definition.responses[min(index, len(definition.responses)) - 1]
                ready_at = time.monotonic() + response.delay_seconds
                while True:
                    self._ensure_open()
                    now = time.monotonic()
                    if now >= deadline:
                        raise ToolTimeoutError("Tool call exceeded deadline")
                    gate_ready = response.gate is None or self._gates[response.gate].is_set()
                    if gate_ready and now >= ready_at:
                        break
                    self._condition.wait(min(deadline - now, ready_at - now) if now < ready_at else deadline - now)
                if not response.is_error:
                    candidate = copy.deepcopy(self._state)
                    changes = []
                    for effect in response.effects:
                        value = copy.deepcopy(effect.value)
                        if effect.argument_path is not None:
                            value = args
                            try:
                                for part in effect.argument_path:
                                    if isinstance(value, dict) and type(part) is str:
                                        value = value[part]
                                    elif isinstance(value, list) and type(part) is int:
                                        value = value[part]
                                    else:
                                        raise KeyError(part)
                            except (KeyError, IndexError) as exc:
                                raise ToolValidationError("Effect argument path is missing") from exc
                        before = copy.deepcopy(candidate.get(effect.key))
                        if effect.operation == "set":
                            candidate[effect.key] = copy.deepcopy(value)
                        elif effect.operation == "append":
                            if effect.key not in candidate:
                                candidate[effect.key] = []
                            if not isinstance(candidate[effect.key], list):
                                raise ToolValidationError("Append target must be an array")
                            candidate[effect.key].append(copy.deepcopy(value))
                        else:
                            current = candidate.get(effect.key, 0)
                            if type(current) not in (int, float) or type(value) not in (int, float):
                                raise ToolValidationError("Increment requires numeric state and value")
                            candidate[effect.key] = current + value
                        changes.append({"operation": effect.operation, "key": effect.key,
                                        "before": before, "after": copy.deepcopy(candidate[effect.key])})
                    candidate = _json_copy(candidate)
                    if time.monotonic() >= deadline:
                        raise ToolTimeoutError("Tool call exceeded deadline before effects")
                    self._state = candidate
                    for change in changes:
                        self._emit("side_effect", {**data, **change}, correlation_id)
                if response.completion_gate is not None:
                    while not self._gates[response.completion_gate].is_set():
                        self._ensure_open()
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise ToolTimeoutError(
                                "Tool call exceeded deadline after effects"
                            )
                        self._condition.wait(remaining)
                self._emit("failed" if response.is_error else "completed",
                           {**data, "arguments": args, "body": copy.deepcopy(response.body),
                            "content_type": response.content_type, "is_error": response.is_error}, correlation_id)
                return copy.deepcopy(response)
            except Exception as exc:
                if self._healthy:
                    self._emit("failed", {**data, "error_type": type(exc).__name__}, correlation_id)
                raise
            finally:
                self._inflight -= 1
                self._condition.notify_all()
