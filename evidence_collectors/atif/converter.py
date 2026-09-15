"""Convert the internal high-fidelity Agent Trace into portable ATIF."""

from __future__ import annotations

import json
from collections.abc import Mapping

from evidence_collectors.atif.model import (
    AtifObservationResult,
    AtifStep,
    AtifToolCall,
    AtifTrajectory,
)
from evidence_collectors.atif.validation import validate_trajectory
from evidence_collectors.trace import (
    AgentTrace,
    JsonValue,
    ModelCall,
    ToolCallStage,
    TraceVisibility,
)


def _text(value: JsonValue | object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _extension(item: object) -> dict[str, JsonValue]:
    return {
        "agent_test_tool": {
            "sequence": getattr(item, "sequence", None),
            "phase": getattr(getattr(item, "phase", None), "value", None),
            "visibility": getattr(getattr(item, "visibility", None), "value", None),
            "ready_state": getattr(getattr(item, "ready_state", None), "value", None),
            "source": getattr(item, "source", None),
            "limitations": list(getattr(item, "limitations", ())),
        }
    }


class AtifConverter:
    """Create one ATIF trajectory for each session in an AgentTrace."""

    def convert(self, trace: AgentTrace) -> tuple[AtifTrajectory, ...]:
        trajectories = tuple(self._convert_session(trace, session) for session in trace.sessions)
        for trajectory in trajectories:
            validate_trajectory(trajectory)
        return trajectories

    def _convert_session(self, trace: AgentTrace, session) -> AtifTrajectory:
        steps: list[AtifStep] = []
        models: list[str] = []
        for turn in sorted(session.turns, key=lambda item: item.sequence):
            steps.append(
                AtifStep(
                    step_id=len(steps) + 1,
                    source="user",
                    message=_text(turn.to_payload()["user_input"]),
                    timestamp=turn.started_at,
                    extra={
                        "agent_test_tool": {
                            "turn_id": turn.turn_id,
                            "sequence": turn.sequence,
                            "ready_state": turn.ready_state.value,
                            "limitations": list(turn.limitations),
                        }
                    },
                )
            )
            for call in sorted(turn.model_calls, key=lambda item: item.sequence):
                if call.model:
                    models.append(call.model)
                steps.append(self._model_step(len(steps) + 1, turn.turn_id, call))
            for effect in sorted(turn.runtime_effects, key=lambda item: item.sequence):
                steps.append(
                    AtifStep(
                        step_id=len(steps) + 1,
                        source="system",
                        message="",
                        timestamp=effect.observed_at,
                        extra={
                            "agent_test_tool": {
                                "turn_id": turn.turn_id,
                                "runtime_effect": effect.to_payload(),
                            }
                        },
                    )
                )
        trajectory = AtifTrajectory(
            session_id=session.session_id,
            trajectory_id=f"{trace.run_id}:{session.session_id}",
            agent_name=trace.product,
            model_name=models[0] if models and len(set(models)) == 1 else None,
            steps=tuple(steps),
            notes="Converted from evaluator-observed AgentTrace; no hidden reasoning inferred.",
            extra={
                "agent_test_tool": {
                    "run_id": trace.run_id,
                    "test_case_id": trace.test_case_id,
                    "trace_schema_version": trace.schema_version,
                    "trace_ready_state": trace.ready_state.value,
                    "collector_health": trace.collector_health,
                    "lost_event_count": trace.lost_event_count,
                    "trace_limitations": list(trace.limitations),
                    "session_ready_state": session.ready_state.value,
                    "session_limitations": list(session.limitations),
                }
            },
        )
        return trajectory

    def _model_step(self, step_id: int, turn_id: str, call: ModelCall) -> AtifStep:
        response_messages = [
            item
            for item in sorted(call.messages, key=lambda item: item.sequence)
            if item.phase.value == "response" and item.role in {"assistant", "agent"}
        ]
        current_messages = [
            item for item in response_messages if item.visibility is TraceVisibility.CURRENT
        ]
        chosen_messages = current_messages or response_messages
        reasoning = [
            item
            for item in sorted(call.reasoning, key=lambda item: item.sequence)
            if item.visibility is TraceVisibility.CURRENT
        ]
        calls_by_id = {}
        lifecycle = {}
        for item in sorted(call.tool_calls, key=lambda item: item.sequence):
            lifecycle.setdefault(item.tool_call_id, []).append(item.to_payload())
            if item.visibility is TraceVisibility.CURRENT:
                calls_by_id[item.tool_call_id] = item
        results_by_id = {}
        for item in sorted(call.tool_results, key=lambda item: item.sequence):
            lifecycle.setdefault(item.tool_call_id, []).append(item.to_payload())
            if item.visibility is TraceVisibility.CURRENT:
                previous = results_by_id.get(item.tool_call_id)
                if previous is None or item.stage is ToolCallStage.RETURNED:
                    results_by_id[item.tool_call_id] = item
        tool_calls = tuple(
            AtifToolCall(
                tool_call_id=item.tool_call_id,
                function_name=item.name,
                arguments=(
                    dict(item.to_payload()["arguments"])
                    if isinstance(item.to_payload()["arguments"], Mapping)
                    else {"value": item.to_payload()["arguments"]}
                ),
                extra=_extension(item),
            )
            for item in calls_by_id.values()
        )
        observations = tuple(
            AtifObservationResult(
                source_call_id=item.tool_call_id,
                content=_text(item.to_payload()["content"]),
                extra={
                    "agent_test_tool": {
                        **_extension(item)["agent_test_tool"],
                        "is_error": item.is_error,
                    }
                },
            )
            for item in results_by_id.values()
        )
        return AtifStep(
            step_id=step_id,
            source="agent",
            message="\n".join(_text(item.to_payload()["content"]) for item in chosen_messages),
            timestamp=call.completed_at or call.started_at,
            model_name=call.model,
            reasoning_content=(
                "\n".join(_text(item.to_payload()["content"]) for item in reasoning)
                if reasoning
                else None
            ),
            tool_calls=tool_calls,
            observation_results=observations,
            is_copied_context=(
                bool(response_messages)
                and all(item.visibility is not TraceVisibility.CURRENT for item in response_messages)
            ),
            llm_call_count=1,
            extra={
                "agent_test_tool": {
                    "turn_id": turn_id,
                    "model_call_id": call.model_call_id,
                    "request_id": call.request_id,
                    "provider": call.provider,
                    "endpoint": call.endpoint,
                    "ready_state": call.ready_state.value,
                    "limitations": list(call.limitations),
                    "tool_lifecycle": lifecycle,
                }
            },
        )
