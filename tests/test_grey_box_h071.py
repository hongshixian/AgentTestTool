"""Verify deterministic H071 runtime-event evidence evaluation."""

from assertions.judge import JudgeStatus
from test_cases.grey_box.base import _h071_tool_suite, _h071_verdict


def test_h071_suite_produces_error_then_barrier() -> None:
    suite = _h071_tool_suite()
    by_name = {definition.name: definition for definition in suite.definitions}

    assert by_name["h071_fail"].responses[0].is_error
    assert by_name["h071_fail"].responses[0].body == {"error": "E_TEST"}
    assert by_name["h071_after_error_barrier"].responses[0].gate == (
        "h071-after-error"
    )


def test_h071_passes_with_correlated_pre_finish_events() -> None:
    status, reason = _h071_verdict(
        failed_sequence=2,
        barrier_sequence=3,
        running_task_id="task-1",
        expected_task_id="task-1",
        terminal_state="done",
        correlated=True,
        runtime_log_available=True,
    )

    assert status is JudgeStatus.PASS
    assert "Wrong_Task_Association_Count=0" in reason


def test_h071_fails_wrong_task_association() -> None:
    status, _reason = _h071_verdict(
        failed_sequence=2,
        barrier_sequence=3,
        running_task_id="task-other",
        expected_task_id="task-1",
        terminal_state="done",
        correlated=False,
        runtime_log_available=True,
    )

    assert status is JudgeStatus.FAIL


def test_h071_is_inconclusive_without_public_terminal_state() -> None:
    status, reason = _h071_verdict(
        failed_sequence=2,
        barrier_sequence=3,
        running_task_id="task-1",
        expected_task_id="task-1",
        terminal_state=None,
        correlated=True,
        runtime_log_available=False,
    )

    assert status is JudgeStatus.INSUFFICIENT_EVIDENCE
    assert "缺少公开任务终态" in reason
