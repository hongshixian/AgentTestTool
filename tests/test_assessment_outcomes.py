"""Verify workbook-aligned assessment outcomes and pytest rendering."""

from types import SimpleNamespace

import pytest

from assertions import (
    ASSESSMENT_MISSING_EVIDENCE_PROPERTY,
    ASSESSMENT_STATUS_PROPERTY,
    AssessmentOutcomeSignal,
    AssessmentStatus,
    assessment_verdict,
    mock_inconclusive_assertion,
)
from test_cases.base import AgentTestCase
from test_cases.conftest import _apply_assessment_signal, pytest_report_teststatus


class TestAssessmentOutcomes:
    def test_statuses_match_the_authoritative_workbook(self) -> None:
        assert {status.value for status in AssessmentStatus} == {
            "通过",
            "不通过",
            "不适用",
            "无法判定",
        }

    def test_mock_assertion_returns_inconclusive_with_missing_evidence(self) -> None:
        verdict = mock_inconclusive_assertion(
            reason="缺少产品安全日志",
            missing_evidence=("输入检测事件", "安全日志"),
        )

        assert verdict.status is AssessmentStatus.INCONCLUSIVE
        assert verdict.reason == "缺少产品安全日志"
        assert verdict.missing_evidence == ("输入检测事件", "安全日志")

    @pytest.mark.parametrize(
        ("reason", "missing_evidence"),
        [
            ("", ("安全日志",)),
            ("证据不足", ()),
            ("证据不足", ("",)),
        ],
    )
    def test_mock_assertion_requires_a_reason_and_specific_missing_evidence(
        self,
        reason: str,
        missing_evidence: tuple[str, ...],
    ) -> None:
        with pytest.raises(ValueError):
            mock_inconclusive_assertion(
                reason=reason,
                missing_evidence=missing_evidence,
            )

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (AssessmentStatus.PASS, ("assessment_passed", ".", "通过")),
            (AssessmentStatus.FAIL, ("assessment_failed", "F", "不通过")),
            (AssessmentStatus.NOT_APPLICABLE, ("not_applicable", "N", "不适用")),
            (AssessmentStatus.INCONCLUSIVE, ("inconclusive", "I", "无法判定")),
        ],
    )
    def test_pytest_renders_all_four_explicit_assessment_states(
        self,
        status: AssessmentStatus,
        expected: tuple[str, str, str],
    ) -> None:
        report = SimpleNamespace(
            when="call",
            user_properties=[(ASSESSMENT_STATUS_PROPERTY, status.value)],
        )

        assert pytest_report_teststatus(report, None) == expected

    @pytest.mark.parametrize(
        "report",
        [
            SimpleNamespace(when="setup", user_properties=[]),
            SimpleNamespace(when="call", user_properties=[]),
            SimpleNamespace(
                when="teardown",
                user_properties=[
                    (ASSESSMENT_STATUS_PROPERTY, AssessmentStatus.INCONCLUSIVE.value)
                ],
            ),
        ],
    )
    def test_pytest_keeps_other_outcomes_unchanged(self, report: object) -> None:
        assert pytest_report_teststatus(report, None) is None

    def test_case_records_inconclusive_before_ending_the_pytest_call(self) -> None:
        events: list[tuple[str, str, object]] = []
        ledger = SimpleNamespace(
            record=lambda source, kind, data: events.append((source, kind, data))
        )
        model = SimpleNamespace(environment=SimpleNamespace(ledger=ledger))
        request = SimpleNamespace(node=SimpleNamespace(user_properties=[]))

        with pytest.raises(AssessmentOutcomeSignal, match="无法判定：缺少产品事件"):
            AgentTestCase().conclude_inconclusive(
                request,
                model,
                reason="缺少产品事件",
                missing_evidence=("安全日志",),
            )

        assert (ASSESSMENT_STATUS_PROPERTY, "无法判定") in request.node.user_properties
        assert events[0][0:2] == ("assertion", "assessment_concluded")

    @pytest.mark.parametrize(
        ("method_name", "status"),
        [
            ("conclude_passed", AssessmentStatus.PASS),
            ("conclude_failed", AssessmentStatus.FAIL),
            ("conclude_not_applicable", AssessmentStatus.NOT_APPLICABLE),
        ],
    )
    def test_case_explicitly_emits_each_terminal_assertion(
        self,
        method_name: str,
        status: AssessmentStatus,
    ) -> None:
        ledger = SimpleNamespace(record=lambda *_args: None)
        model = SimpleNamespace(environment=SimpleNamespace(ledger=ledger))
        request = SimpleNamespace(node=SimpleNamespace(user_properties=[]))

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            getattr(AgentTestCase(), method_name)(
                request,
                model,
                reason="明确的用例结论",
            )

        assert outcome.value.verdict.status is status
        assert (ASSESSMENT_STATUS_PROPERTY, status.value) in request.node.user_properties

    @pytest.mark.parametrize(
        ("status", "expected_outcome"),
        [
            (AssessmentStatus.PASS, "passed"),
            (AssessmentStatus.FAIL, "failed"),
            (AssessmentStatus.NOT_APPLICABLE, "passed"),
            (AssessmentStatus.INCONCLUSIVE, "passed"),
        ],
    )
    def test_four_state_signal_never_becomes_pytest_skip(
        self,
        status: AssessmentStatus,
        expected_outcome: str,
    ) -> None:
        verdict = (
            mock_inconclusive_assertion(
                reason="证据不足",
                missing_evidence=("安全日志",),
            )
            if status is AssessmentStatus.INCONCLUSIVE
            else assessment_verdict(status, reason="明确结果")
        )
        report = SimpleNamespace(
            outcome="failed",
            longrepr="traceback",
            user_properties=[],
        )

        _apply_assessment_signal(report, AssessmentOutcomeSignal(verdict))

        assert report.outcome == expected_outcome
        assert report.outcome != "skipped"
        assert (ASSESSMENT_STATUS_PROPERTY, status.value) in report.user_properties
        assert any(
            name == ASSESSMENT_MISSING_EVIDENCE_PROPERTY
            for name, _value in report.user_properties
        )
