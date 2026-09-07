"""Assert observable controlled-environment behavior without inferring hidden facts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ObservationWindow:
    """An exclusive sequence window within one collector and one run.

    Boundary sequences identify environment observation_started/observation_ended
    events naming the target tool, not arbitrary events or clock values.
    A zero-call assertion additionally requires healthy receiver probes bracketing
    the window and a successful normal baseline of the same tool before it.
    The baseline must traverse HTTP reception, runtime reception/completion and
    HTTP response in order. This proves that local route, not caller identity.
    """

    run_id: str
    start_sequence: int
    end_sequence: int
    baseline_correlation_id: str

    def __post_init__(self) -> None:
        if not self.run_id or not self.baseline_correlation_id:
            raise ValueError("Window run and baseline correlation are required")
        if type(self.start_sequence) is not int or type(self.end_sequence) is not int or not 0 < self.start_sequence < self.end_sequence:
            raise ValueError("Window boundaries must be increasing positive sequences")


def assert_collector_healthy(collector_or_health: Any) -> None:
    """Require positive, explicit evidence collection health, not absence of errors alone."""
    health = collector_or_health.health() if callable(getattr(collector_or_health, "health", None)) else collector_or_health
    assert isinstance(health, Mapping), "缺少明确的采集健康状态"
    assert health.get("healthy") is True, "证据采集不健康，不能给出通过结论"
    assert health.get("errors") == [], "采集错误清单缺失或包含错误"


def _observations(collector_or_events: Any, health: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if callable(getattr(collector_or_events, "snapshot", None)):
        events = collector_or_events.snapshot()
        current = collector_or_events.health()
    else:
        events, current = collector_or_events, health
    assert_collector_healthy(current)
    assert isinstance(events, Sequence) and not isinstance(events, (str, bytes)), "证据必须是事件列表"
    assert isinstance(current, Mapping)
    assert current.get("event_count") == len(events), "健康状态与事件快照数量不一致"
    run_id = current.get("run_id")
    assert isinstance(run_id, str) and run_id, "采集健康状态缺少运行标识"
    for index, event in enumerate(events, 1):
        assert isinstance(event, Mapping), "证据事件格式错误"
        assert type(event.get("sequence")) is int and event["sequence"] == index, "事件序列缺失、重复或重排"
        assert event.get("run_id") == run_id, "不可混用不同运行的证据"
        assert isinstance(event.get("data"), Mapping), "环境事件 data 必须是对象"
    return list(events)


def _in_window(events: list[Mapping[str, Any]], window: ObservationWindow | None) -> list[Mapping[str, Any]]:
    if window is None:
        return events
    assert events and all(event["run_id"] == window.run_id for event in events), "观察窗口与运行标识不一致"
    assert window.end_sequence <= len(events), "观察窗口尚未结束或缺少结束证据"
    return [event for event in events if window.start_sequence < event["sequence"] < window.end_sequence]


def _calls(events: list[Mapping[str, Any]], tool_name: str) -> list[Mapping[str, Any]]:
    assert isinstance(tool_name, str) and tool_name, "必须指定单个工具名称"
    return [event for event in events if event.get("source") == "tool_runtime"
            and event.get("kind") == "received" and event["data"].get("tool_name") == tool_name]


def assert_tool_call_count(collector_or_events: Any, tool_name: str, expected: int, *, window: ObservationWindow | None = None,
                           health: Mapping[str, Any] | None = None) -> None:
    """Count received attempts, including failed calls, only for the specified tool."""
    assert type(expected) is int and expected >= 0, "预期调用次数必须是非负整数"
    if expected == 0:
        assert window is not None, "零调用断言必须提供完整观察窗口"
        assert_no_tool_calls(collector_or_events, tool_name, window=window, health=health)
        return
    events = _in_window(_observations(collector_or_events, health), window)
    assert len(_calls(events, tool_name)) == expected, "指定工具的实际接收调用次数不符合预期"


def assert_no_tool_calls(collector_or_events: Any, tool_name: str, *, window: ObservationWindow,
                         health: Mapping[str, Any] | None = None) -> None:
    """Assert local zero reception, not universal non-execution or non-exfiltration."""
    events = _observations(collector_or_events, health)
    selected = _in_window(events, window)
    _calls([], tool_name)
    start, end = events[window.start_sequence - 1], events[window.end_sequence - 1]
    for event, kind in ((start, "observation_started"), (end, "observation_ended")):
        assert (event.get("source") == "environment" and event.get("kind") == kind
                and event["data"].get("tool_name") == tool_name), "观察窗口必须由指定工具的明确开始与结束事件界定"
    before = [event for event in events if event["sequence"] < window.start_sequence]
    after = [event for event in events if event["sequence"] > window.end_sequence]
    probe = lambda event: (event.get("source") == "http_receiver" and event.get("kind") == "health_probe"
                           and event["data"].get("healthy") is True)
    assert any(probe(event) for event in before), "观察窗口前缺少真实接收端健康探测"
    assert any(probe(event) for event in after), "观察窗口后缺少真实接收端健康探测"
    baseline = [event for event in before if event.get("correlation_id") == window.baseline_correlation_id]
    received = _calls(baseline, tool_name)
    completed = [event for event in baseline if event.get("source") == "tool_runtime" and event.get("kind") == "completed"
                 and event["data"].get("tool_name") == tool_name and event["data"].get("is_error") is False]
    assert len(received) == len(completed) == 1 and received[0]["sequence"] < completed[0]["sequence"], "缺少同一指定工具的成功正常调用基线"
    http_received = [event for event in baseline if event.get("source") == "http_receiver"
                     and event.get("kind") == "http_received" and event["data"].get("method") == "POST"
                     and event["data"].get("route") == "/call"]
    http_responded = [event for event in baseline if event.get("source") == "http_receiver"
                      and event.get("kind") == "http_responded" and event["data"].get("name") == tool_name]
    assert len(http_received) == len(http_responded) == 1, "正常基线必须经过实际 HTTP 工具调用通道"
    assert (http_received[0]["sequence"] < received[0]["sequence"] < completed[0]["sequence"]
            < http_responded[0]["sequence"]), "正常基线的 HTTP 与工具执行事件顺序不完整"
    assert not any(event.get("kind") == "failed" for event in baseline), "正常调用基线包含失败事件"
    assert not _calls(selected, tool_name), "指定工具在观察窗口内收到了调用"


def _equal_json(actual: Any, expected: Any) -> bool:
    try:
        observed = json.dumps(actual, sort_keys=True, ensure_ascii=False, allow_nan=False)
        desired = json.dumps(expected, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise AssertionError("断言值必须是有效 JSON") from None
    assert "[REDACTED]" not in observed, "已脱敏字段不能用于推断其原始值"
    return observed == desired


def assert_tool_arguments(collector_or_events: Any, tool_name: str, expected_arguments: Mapping[str, Any], *,
                          correlation_id: str | None = None, window: ObservationWindow | None = None,
                          health: Mapping[str, Any] | None = None) -> None:
    """Require one unambiguous received call with exactly the specified arguments."""
    events = _in_window(_observations(collector_or_events, health), window)
    calls = _calls(events, tool_name)
    if correlation_id is not None:
        calls = [event for event in calls if event.get("correlation_id") == correlation_id]
    assert len(calls) == 1, "调用不存在或不唯一，请指定独立的调用关联标识"
    assert "arguments" in calls[0]["data"], "缺少实际接收参数"
    assert _equal_json(calls[0]["data"]["arguments"], expected_arguments), "指定工具的实际参数不符合预期"


def assert_simulated_state(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    """Compare controlled simulated business state, not the product's backend state."""
    assert isinstance(actual, Mapping) and isinstance(expected, Mapping), "模拟状态必须是对象"
    assert _equal_json(actual, expected), "受控模拟业务状态不符合预期"


def assert_simulated_effect(collector_or_events: Any, tool_name: str, key: str, before: Any, after: Any, *,
                            correlation_id: str | None = None, window: ObservationWindow | None = None,
                            health: Mapping[str, Any] | None = None) -> None:
    """Require a recorded simulated effect and completed call in the same local stream."""
    events = _in_window(_observations(collector_or_events, health), window)
    effects = [event for event in events if event.get("source") == "tool_runtime" and event.get("kind") == "side_effect"
               and event["data"].get("tool_name") == tool_name and event["data"].get("key") == key
               and (correlation_id is None or event.get("correlation_id") == correlation_id)]
    assert len(effects) == 1, "模拟副作用不存在或不唯一"
    effect = effects[0]
    assert "before" in effect["data"] and "after" in effect["data"], "缺少模拟副作用前后值"
    assert _equal_json(effect["data"]["before"], before) and _equal_json(effect["data"]["after"], after), "模拟副作用前后值不符合预期"
    call_id = effect.get("correlation_id")
    assert isinstance(call_id, str) and call_id, "模拟副作用缺少调用关联标识"
    received = [event for event in _calls(events, tool_name) if event.get("correlation_id") == call_id]
    completed = [event for event in events if event.get("source") == "tool_runtime" and event.get("kind") == "completed"
                 and event.get("correlation_id") == call_id and event["data"].get("tool_name") == tool_name
                 and event["data"].get("is_error") is False]
    assert len(received) == len(completed) == 1, "副作用缺少完整调用生命周期"
    assert received[0]["sequence"] < effect["sequence"] < completed[0]["sequence"], "模拟调用与副作用事件顺序异常"


def assert_event_order(collector_or_events: Any, before_sequence: int, after_sequence: int, *,
                       health: Mapping[str, Any] | None = None) -> None:
    """Check collector order within one correlated operation, not distributed causality."""
    events = _observations(collector_or_events, health)
    assert type(before_sequence) is int and type(after_sequence) is int, "事件序号必须是整数"
    assert 1 <= before_sequence < after_sequence <= len(events), "缺少顺序证据或事件顺序不符合预期"
    before, after = events[before_sequence - 1], events[after_sequence - 1]
    correlation = before.get("correlation_id")
    assert isinstance(correlation, str) and correlation and correlation == after.get("correlation_id"), "不能从不同操作的采集顺序推断因果关系"
