"""Verify the CodeBuddy black-box observation command adapter."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from agent_models import (
    AgentEvent,
    AgentEventType,
    EvidenceAuthority,
    EvidenceBundle,
    EvidencePhase,
    EvidenceRequest,
    EvidenceStatus,
    RequestContext,
)
from agent_models.codebuddy.evidence import (
    CodeBuddyCommandEvidenceProvider,
    CodeBuddyStreamEvidenceAdapter,
)


class TestCodeBuddyCommandEvidenceProvider:
    def test_reads_json_evidence_from_command(self, tmp_path) -> None:
        command = (
            sys.executable,
            "-c",
            "import json; print(json.dumps({'evidence': [{'evidence_id': "
            "'authoritative_identity_observation', 'type': 'environment_observation', "
            "'data': {'user_id': 'user-a', 'instance_id': 'instance-a'}}]}))",
        )
        provider = CodeBuddyCommandEvidenceProvider(workspace=tmp_path, command=command)

        records = provider.capture(_request())

        assert len(records) == 1
        assert records[0].evidence_id == "authoritative_identity_observation"
        assert records[0].phase is EvidencePhase.BEFORE

    def test_preserves_structured_source_status_and_correlation(self, tmp_path) -> None:
        command = (
            sys.executable,
            "-c",
            "import json; print(json.dumps({'evidence': [{'evidence_id': 'identity', "
            "'type': 'runtime_evidence', 'status': 'available', 'data': {'id': 'u1'}, "
            "'source': {'provider': 'public-api', 'channel': 'whoami', "
            "'authority': 'product_public_api', 'product_version': '1.2.3'}, "
            "'correlation': {'request_ids': ['r1']}, 'proves': ['current user'], "
            "'limitations': ['current account only']}]}))",
        )
        provider = CodeBuddyCommandEvidenceProvider(workspace=tmp_path, command=command)

        record = provider.capture(_request())[0]

        assert record.source is not None
        assert record.source.authority is EvidenceAuthority.PRODUCT_PUBLIC_API
        assert record.source.product_version == "1.2.3"
        assert record.correlation.run_id == "test-run"
        assert record.correlation.request_ids == ("r1",)
        assert record.proves == ("current user",)
        assert record.limitations == ("current account only",)

    def test_failure_payload_contains_no_injected_credentials(self, tmp_path) -> None:
        command = (
            sys.executable,
            "-c",
            "import sys; print(sys.stdin.read(), file=sys.stderr); raise SystemExit(2)",
        )
        provider = CodeBuddyCommandEvidenceProvider(workspace=tmp_path, command=command)

        with pytest.raises(RuntimeError) as captured:
            provider.capture(_request())

        assert "authorization" not in str(captured.value)
        assert "Bearer" not in str(captured.value)

    def test_observation_command_does_not_inherit_judge_or_test_secrets(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            os,
            "environ",
            {
                "JUDGE_API_KEY": "fake-judge-secret",
                "AGENT_TEST_SECRET": "fake-test-secret",
                "CODEBUDDY_API_KEY": "fake-product-key",
                "PATH": "/fake/bin",
            },
        )
        calls = []

        def run(command, **kwargs):
            calls.append(kwargs)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"evidence": []}',
                stderr="",
            )

        monkeypatch.setattr(subprocess, "run", run)
        provider = CodeBuddyCommandEvidenceProvider(
            workspace=tmp_path,
            command=(sys.executable, "fixture"),
        )

        assert provider.capture(_request()) == ()
        assert calls[0]["env"] == {
            "CODEBUDDY_API_KEY": "fake-product-key",
            "PATH": "/fake/bin",
        }

    @pytest.mark.parametrize(
        ("extra", "message"),
        [
            ("'status': 'not-a-status',", "status"),
            (
                "'source': {'provider': 'api', 'channel': 'identity', "
                "'authority': 'invented'},",
                "authority",
            ),
            ("'correlation': {'request_ids': 'not-a-list'},", "列表字段"),
        ],
    )
    def test_invalid_evidence_metadata_fails_closed(
        self, tmp_path, extra: str, message: str
    ) -> None:
        script = (
            "import json; print(json.dumps({'evidence': [{'evidence_id': 'item', "
            f"'type': 'runtime_evidence', {extra} 'data': {{}}}}]}}))"
        )
        provider = CodeBuddyCommandEvidenceProvider(
            workspace=tmp_path,
            command=(sys.executable, "-c", script),
        )

        with pytest.raises(RuntimeError, match=message):
            provider.capture(_request())

    def test_observation_timeout_fails_instead_of_returning_empty_evidence(
        self, tmp_path, monkeypatch
    ) -> None:
        provider = CodeBuddyCommandEvidenceProvider(
            workspace=tmp_path,
            command=(sys.executable, "fixture"),
            default_timeout=0.1,
        )

        def timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired("fixture", 0.1)

        monkeypatch.setattr(subprocess, "run", timeout)

        with pytest.raises(RuntimeError, match="超时"):
            provider.capture(_request())

    @pytest.mark.parametrize(
        ("correlation", "message"),
        [
            ({"run_id": "other-run"}, "run_id"),
            ({"session_ids": ["other-session"]}, "session_id"),
        ],
    )
    def test_mismatched_evidence_correlation_fails_closed(
        self, tmp_path, correlation: dict[str, object], message: str
    ) -> None:
        script = (
            "import json; print(json.dumps({'evidence': [{'evidence_id': 'item', "
            "'type': 'runtime_evidence', 'data': {}, 'correlation': "
            f"{correlation!r}" + "}]}))"
        )
        provider = CodeBuddyCommandEvidenceProvider(
            workspace=tmp_path,
            command=(sys.executable, "-c", script),
        )
        request = _request()
        request = EvidenceRequest(
            request.sample_id,
            request.prompt_id,
            request.repeat_index,
            request.phase,
            request.context,
            session_id="expected-session",
        )

        with pytest.raises(RuntimeError, match=message):
            provider.capture(request)


class TestCodeBuddyStreamEvidenceAdapter:
    def test_complete_window_exposes_only_bounded_runtime_claims(self) -> None:
        request = EvidenceRequest(
            "sample",
            "prompt",
            1,
            EvidencePhase.AFTER,
            session_id="session-1",
        )
        events = (
            _event(1, AgentEventType.SESSION_STARTED),
            _event(2, AgentEventType.USER_INPUT, turn_id="turn-1"),
            _event(
                3,
                AgentEventType.TOOL_CALL,
                turn_id="turn-1",
                request_id="request-1",
                data={"id": "tool-1", "name": "Read"},
            ),
            _event(
                4,
                AgentEventType.PERMISSION_REQUEST,
                turn_id="turn-1",
                request_id="permission-1",
                data={"tool_use_id": "tool-1"},
            ),
            _event(
                5,
                AgentEventType.PERMISSION_DECISION,
                turn_id="turn-1",
                request_id="permission-1",
                data={"tool_use_id": "tool-1", "decision": "allow"},
            ),
            _event(
                6,
                AgentEventType.TASK_STARTED,
                turn_id="turn-1",
                data={"task_id": "task-1"},
            ),
            _event(
                7,
                AgentEventType.CONTROL_REQUEST,
                turn_id="turn-1",
                request_id="control-1",
                data={"subtype": "interrupt"},
            ),
            _event(
                8,
                AgentEventType.CONTROL_RESPONSE,
                turn_id="turn-1",
                request_id="control-1",
                data={"subtype": "success"},
            ),
            _event(
                9,
                AgentEventType.TURN_COMPLETED,
                turn_id="turn-1",
                request_id="request-1",
            ),
        )

        records = CodeBuddyStreamEvidenceAdapter().capture(
            request,
            events=events,
            run_id="run-1",
            product_version="fixture-version",
        )
        bundle = EvidenceBundle("sample", "prompt", "run-1", (), records)

        assert {
            "agent_runtime_stream",
            "agent_session_correlation",
            "agent_tool_events",
            "agent_permission_events",
            "agent_runtime_control",
            "agent_task_events",
        } <= bundle.available_evidence_ids
        runtime = records[0]
        assert runtime.status is EvidenceStatus.AVAILABLE
        assert runtime.source is not None
        assert runtime.source.authority is EvidenceAuthority.PRODUCT_RUNTIME
        assert runtime.correlation.run_id == "run-1"
        assert runtime.correlation.session_ids == ("session-1",)
        assert runtime.correlation.request_ids == (
            "request-1",
            "permission-1",
            "control-1",
        )
        assert runtime.correlation.task_ids == ("task-1",)
        assert runtime.correlation.tool_use_ids == ("tool-1",)
        assert any("不证明云端账号身份" in item for item in runtime.limitations)

    def test_incomplete_window_is_preserved_but_not_available(self) -> None:
        request = EvidenceRequest(
            "sample", "prompt", 1, EvidencePhase.AFTER, session_id="session-1"
        )

        records = CodeBuddyStreamEvidenceAdapter().capture(
            request,
            events=(_event(1, AgentEventType.SESSION_STARTED),),
            run_id="run-1",
        )

        assert records[0].status is EvidenceStatus.UNVERIFIED
        assert EvidenceBundle(
            "sample", "prompt", "run-1", (), records
        ).available_evidence_ids == frozenset()

    def test_later_unfinished_turn_invalidates_the_whole_window(self) -> None:
        request = EvidenceRequest(
            "sample", "prompt", 1, EvidencePhase.AFTER, session_id="session-1"
        )
        events = (
            _event(1, AgentEventType.SESSION_STARTED),
            _event(2, AgentEventType.USER_INPUT, turn_id="turn-1"),
            _event(3, AgentEventType.TURN_COMPLETED, turn_id="turn-1"),
            _event(4, AgentEventType.USER_INPUT, turn_id="turn-2"),
        )

        runtime = CodeBuddyStreamEvidenceAdapter().capture(
            request, events=events, run_id="run-1"
        )[0]

        assert runtime.status is EvidenceStatus.UNVERIFIED
        assert runtime.data["observation_window"]["incomplete_turn_ids"] == [
            "turn-2"
        ]

    def test_protocol_error_marks_runtime_source_unavailable(self) -> None:
        request = EvidenceRequest(
            "sample", "prompt", 1, EvidencePhase.AFTER, session_id="session-1"
        )
        events = (
            _event(1, AgentEventType.SESSION_STARTED),
            _event(2, AgentEventType.USER_INPUT, turn_id="turn-1"),
            _event(3, AgentEventType.PROTOCOL_ERROR, turn_id="turn-1"),
        )

        runtime = CodeBuddyStreamEvidenceAdapter().capture(
            request, events=events, run_id="run-1"
        )[0]

        assert runtime.status is EvidenceStatus.ERROR
        assert runtime.data["observation_window"]["protocol_error_observed"] is True

    @pytest.mark.parametrize("corruption", ["out_of_order", "duplicate_terminal"])
    def test_corrupted_event_order_or_duplicate_terminal_is_unavailable(
        self, corruption: str
    ) -> None:
        events = (
            (
                _event(1, AgentEventType.USER_INPUT, turn_id="turn-1"),
                _event(3, AgentEventType.SESSION_STARTED, turn_id="turn-1"),
                _event(2, AgentEventType.TURN_COMPLETED, turn_id="turn-1"),
            )
            if corruption == "out_of_order"
            else (
                _event(1, AgentEventType.SESSION_STARTED, turn_id="turn-1"),
                _event(2, AgentEventType.USER_INPUT, turn_id="turn-1"),
                _event(3, AgentEventType.TURN_COMPLETED, turn_id="turn-1"),
                _event(4, AgentEventType.TURN_COMPLETED, turn_id="turn-1"),
            )
        )
        runtime = CodeBuddyStreamEvidenceAdapter().capture(
            EvidenceRequest(
                "sample", "prompt", 1, EvidencePhase.AFTER, session_id="session-1"
            ),
            events=events,
            run_id="run-1",
        )[0]

        assert runtime.status is EvidenceStatus.ERROR

    def test_turn_correlation_survives_product_session_id_remapping(self) -> None:
        request = EvidenceRequest(
            "sample", "prompt", 1, EvidencePhase.AFTER, session_id="product-session"
        )
        events = (
            _event(
                1,
                AgentEventType.USER_INPUT,
                session_id="requested-session",
                turn_id="turn-1",
            ),
            _event(
                2,
                AgentEventType.SESSION_STARTED,
                session_id="product-session",
                turn_id="turn-1",
            ),
            _event(
                3,
                AgentEventType.TURN_COMPLETED,
                session_id="product-session",
                turn_id="turn-1",
            ),
            _event(
                4,
                AgentEventType.SESSION_EXITED,
                session_id="requested-session",
                data={"returncode": 0},
            ),
        )

        runtime = CodeBuddyStreamEvidenceAdapter().capture(
            request,
            events=events,
            run_id="run-1",
        )[0]

        assert runtime.status is EvidenceStatus.AVAILABLE
        assert runtime.correlation.session_ids == (
            "requested-session",
            "product-session",
        )

    def test_sequential_session_windows_do_not_include_other_session_exit(self) -> None:
        events = (
            _event(
                1,
                AgentEventType.USER_INPUT,
                session_id="requested-1",
                turn_id="turn-1",
            ),
            _event(
                2,
                AgentEventType.SESSION_STARTED,
                session_id="product-1",
                turn_id="turn-1",
            ),
            _event(
                3,
                AgentEventType.TURN_COMPLETED,
                session_id="product-1",
                turn_id="turn-1",
            ),
            _event(
                4,
                AgentEventType.SESSION_EXITED,
                session_id="requested-1",
                data={"returncode": 0},
            ),
            _event(
                1,
                AgentEventType.USER_INPUT,
                session_id="requested-2",
                turn_id="turn-2",
            ),
            _event(
                2,
                AgentEventType.SESSION_STARTED,
                session_id="requested-2",
                turn_id="turn-2",
            ),
            _event(
                3,
                AgentEventType.TURN_COMPLETED,
                session_id="product-2",
                turn_id="turn-2",
            ),
            _event(
                4,
                AgentEventType.SESSION_EXITED,
                session_id="requested-2",
                data={"returncode": 0},
            ),
        )

        runtime = CodeBuddyStreamEvidenceAdapter().capture(
            EvidenceRequest(
                "sample",
                "prompt",
                1,
                EvidencePhase.AFTER,
                session_id="requested-2",
            ),
            events=events,
            run_id="run-1",
        )[0]

        assert runtime.status is EvidenceStatus.AVAILABLE
        assert runtime.correlation.session_ids == ("requested-2", "product-2")
        assert runtime.correlation.turn_ids == ("turn-2",)
        assert runtime.data["observation_window"]["session_exit_observed"] is True

    def test_requested_session_id_disambiguates_reused_product_session_id(self) -> None:
        events = (
            _event(1, AgentEventType.USER_INPUT, session_id="requested-1", turn_id="turn-1"),
            _event(2, AgentEventType.SESSION_STARTED, session_id="product", turn_id="turn-1"),
            _event(3, AgentEventType.TURN_COMPLETED, session_id="product", turn_id="turn-1"),
            _event(4, AgentEventType.SESSION_EXITED, session_id="requested-1", data={"returncode": 0}),
            _event(1, AgentEventType.USER_INPUT, session_id="requested-2", turn_id="turn-2"),
            _event(2, AgentEventType.SESSION_STARTED, session_id="product", turn_id="turn-2"),
            _event(3, AgentEventType.TURN_COMPLETED, session_id="product", turn_id="turn-2"),
            _event(4, AgentEventType.SESSION_EXITED, session_id="requested-2", data={"returncode": 0}),
        )

        runtime = CodeBuddyStreamEvidenceAdapter().capture(
            EvidenceRequest(
                "sample",
                "prompt",
                1,
                EvidencePhase.AFTER,
                session_id="requested-2",
            ),
            events=events,
            run_id="run-1",
        )[0]

        assert runtime.status is EvidenceStatus.AVAILABLE
        assert runtime.correlation.session_ids == ("requested-2", "product")
        assert runtime.correlation.turn_ids == ("turn-2",)


def _request() -> EvidenceRequest:
    return EvidenceRequest(
        sample_id="ATS-5.1b-D5-02-S04",
        prompt_id="LANGUAGE-01",
        repeat_index=1,
        phase=EvidencePhase.BEFORE,
        context=RequestContext(
            user_id="user-a",
            instance_id="instance-a",
            run_id="test-run",
        ),
    )


def _event(
    sequence: int,
    event_type: AgentEventType,
    *,
    session_id: str = "session-1",
    turn_id: str | None = None,
    request_id: str | None = None,
    data=None,
) -> AgentEvent:
    return AgentEvent(
        sequence=sequence,
        event_type=event_type,
        observed_at=f"2026-09-09T00:00:0{sequence}+00:00",
        monotonic_seconds=float(sequence),
        session_id=session_id,
        request_id=request_id,
        turn_id=turn_id,
        data={} if data is None else data,
    )
