"""Verify workbook-aligned assessment outcomes and pytest rendering."""

from types import SimpleNamespace

import pytest

from assertions import (
    ASSESSMENT_STATUS_PROPERTY,
    AssessmentStatus,
    mock_inconclusive_assertion,
)
from test_cases.conftest import pytest_report_teststatus
from test_cases.base import AgentTestCase


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

    def test_pytest_renders_only_marked_call_skips_as_inconclusive(self) -> None:
        report = SimpleNamespace(
            when="call",
            skipped=True,
            user_properties=[
                (ASSESSMENT_STATUS_PROPERTY, AssessmentStatus.INCONCLUSIVE.value)
            ],
        )

        assert pytest_report_teststatus(report, None) == (
            "inconclusive",
            "I",
            "无法判定",
        )

    @pytest.mark.parametrize(
        "report",
        [
            SimpleNamespace(when="setup", skipped=True, user_properties=[]),
            SimpleNamespace(when="call", skipped=True, user_properties=[]),
            SimpleNamespace(
                when="call",
                skipped=False,
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

        with pytest.raises(pytest.skip.Exception, match="无法判定：缺少产品事件"):
            AgentTestCase().conclude_inconclusive(
                request,
                model,
                reason="缺少产品事件",
                missing_evidence=("安全日志",),
            )

        assert (ASSESSMENT_STATUS_PROPERTY, "无法判定") in request.node.user_properties
        assert events[0][0:2] == ("assertion", "assessment_inconclusive")
