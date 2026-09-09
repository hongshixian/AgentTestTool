"""Verify CodeBuddy persistent stream-json interaction without external services."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agent_models import AgentEventType, PermissionDecision
from agent_models.codebuddy.interactive import CodeBuddyInteractiveSession


PROBE = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "framework_fixtures"
    / "interactive_cli_protocol_probe.py"
)


@pytest.fixture
def session(tmp_path: Path) -> CodeBuddyInteractiveSession:
    value = CodeBuddyInteractiveSession(
        command=(sys.executable, "-u", str(PROBE)),
        workspace=tmp_path,
        environment={},
        session_id="offline-session",
        default_timeout=2.0,
    )
    try:
        yield value
    finally:
        value.close()


class TestCodeBuddyInteractiveSession:
    def test_multiple_turns_reuse_one_process_and_preserve_event_order(
        self, session: CodeBuddyInteractiveSession
    ) -> None:
        first = session.send_input("one")
        started = session.wait_for_event(
            AgentEventType.SESSION_STARTED,
            timeout=2.0,
            after_sequence=first.after_sequence,
        )
        first_result = session.wait_for_completion(first)
        second = session.send_input("two")
        second_result = session.wait_for_completion(second)

        assert started.session_id == "offline-session"
        assert first_result.response == "reply:one"
        assert second_result.response == "reply:two"
        assert first_result.session_id == second_result.session_id
        sequences = [event.sequence for event in session.events]
        assert sequences == list(range(1, len(sequences) + 1))

    @pytest.mark.parametrize(
        ("decision", "expected"),
        [
            (PermissionDecision.ALLOW, "allow"),
            (PermissionDecision.DENY, "deny"),
            (PermissionDecision.CANCEL, "cancel"),
        ],
    )
    def test_permission_decisions_are_correlated_by_request_id(
        self,
        session: CodeBuddyInteractiveSession,
        decision: PermissionDecision,
        expected: str,
    ) -> None:
        turn = session.send_input("NEED_PERMISSION")
        request = session.wait_for_event(
            AgentEventType.PERMISSION_REQUEST,
            timeout=2.0,
            after_sequence=turn.after_sequence,
        )

        session.respond_to_confirmation(request, decision, reason="offline decision")
        result = session.wait_for_completion(turn)
        sent_decision = next(
            event
            for event in session.events
            if event.event_type is AgentEventType.PERMISSION_DECISION
            and event.request_id == request.request_id
        )

        assert request.request_id
        assert request.data["tool_use_id"] == "tool-1"
        assert sent_decision.sequence > request.sequence
        assert sent_decision.data["decision"] == decision.value
        assert result.response == f"permission:{expected}"

    def test_steer_controls_an_active_turn(self, session: CodeBuddyInteractiveSession) -> None:
        turn = session.send_input("WAIT")
        session.wait_for_event(
            AgentEventType.TEXT,
            timeout=2.0,
            after_sequence=turn.after_sequence,
        )

        control = session.steer("finish now")
        result = session.wait_for_completion(turn)

        assert control.success
        assert control.data["steered"] is True
        assert result.response == "steered:finish now"
        request_event = next(
            event
            for event in session.events
            if event.event_type is AgentEventType.CONTROL_REQUEST
            and event.request_id == control.request_id
        )
        response_event = next(
            event
            for event in session.events
            if event.event_type is AgentEventType.CONTROL_RESPONSE
            and event.request_id == control.request_id
        )
        assert request_event.sequence < response_event.sequence

    def test_interrupt_ack_is_distinct_from_turn_failure(
        self, session: CodeBuddyInteractiveSession
    ) -> None:
        turn = session.send_input("WAIT")
        session.wait_for_event(
            AgentEventType.TEXT,
            timeout=2.0,
            after_sequence=turn.after_sequence,
        )

        control = session.interrupt_task(reason="offline cancellation")
        result = session.wait_for_completion(turn)

        assert control.success
        assert control.data["interrupted"] is True
        assert not result.completed
        assert "interrupted" in result.stderr

    def test_background_terminal_state_is_normalized(
        self, session: CodeBuddyInteractiveSession
    ) -> None:
        turn = session.send_input("BACKGROUND")
        started = session.wait_for_event(
            AgentEventType.TASK_STARTED,
            timeout=2.0,
            after_sequence=turn.after_sequence,
        )
        completed = session.wait_for_event(
            AgentEventType.TASK_COMPLETED,
            timeout=2.0,
            after_sequence=started.sequence,
        )

        assert completed.data["task_id"] == "task-1"
        assert session.wait_for_completion(turn).completed

    def test_partial_stream_text_is_normalized(
        self, session: CodeBuddyInteractiveSession
    ) -> None:
        turn = session.send_input("PARTIAL")

        partial = session.wait_for_event(
            AgentEventType.TEXT_DELTA,
            timeout=2.0,
            after_sequence=turn.after_sequence,
        )

        assert partial.text == "partial-text"
        assert session.wait_for_completion(turn).completed

    def test_malformed_ndjson_fails_closed(
        self, session: CodeBuddyInteractiveSession
    ) -> None:
        turn = session.send_input("MALFORMED")
        event = session.wait_for_event(
            AgentEventType.PROTOCOL_ERROR,
            timeout=2.0,
            after_sequence=turn.after_sequence,
        )

        assert event.event_type is AgentEventType.PROTOCOL_ERROR
        with pytest.raises(RuntimeError, match="collection failed"):
            session.wait_for_completion(turn)

    def test_wait_uses_a_bounded_deadline(
        self, session: CodeBuddyInteractiveSession
    ) -> None:
        with pytest.raises(TimeoutError, match="task_failed"):
            session.wait_for_event(AgentEventType.TASK_FAILED, timeout=0.01)

    def test_initialize_response_does_not_expose_account_or_token(
        self, session: CodeBuddyInteractiveSession
    ) -> None:
        control = next(
            event
            for event in session.events
            if event.event_type is AgentEventType.CONTROL_RESPONSE
        )

        assert "account" not in str(control.data)
        assert "fixture-secret-token" not in str(control.data)

    def test_close_is_idempotent_and_stops_the_process(
        self, session: CodeBuddyInteractiveSession
    ) -> None:
        session.close()
        session.close()

        assert not session.is_running
        with pytest.raises(RuntimeError, match="closed"):
            session.send_input("after-close")
