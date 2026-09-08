"""Verify workbook-aligned assessment outcomes and pytest rendering."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_models import AuthResult, AuthStatus, TurnResult
from assertions import (
    ASSESSMENT_MISSING_EVIDENCE_PROPERTY,
    ASSESSMENT_STATUS_PROPERTY,
    AssessmentOutcomeSignal,
    AssessmentStatus,
    assessment_verdict,
    mock_inconclusive_assertion,
)
from test_cases.base import AgentTestCase
from test_cases.conftest import (
    _apply_assessment_signal,
    pytest_report_teststatus,
    pytest_runtest_makereport,
)


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
            execution_completed=True,
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
                execution_completed=True,
            )

    def test_mock_assertion_requires_completed_functional_execution(self) -> None:
        with pytest.raises(ValueError, match="目标功能成功执行"):
            mock_inconclusive_assertion(
                reason="证据不足",
                missing_evidence=("安全日志",),
                execution_completed=False,
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

    @pytest.mark.parametrize("phase", ["setup", "teardown"])
    def test_pytest_renders_non_call_framework_failures_as_assessment_fail(
        self,
        phase: str,
    ) -> None:
        report = SimpleNamespace(
            when=phase,
            user_properties=[
                (ASSESSMENT_STATUS_PROPERTY, AssessmentStatus.FAIL.value)
            ],
        )

        assert pytest_report_teststatus(report, None) == (
            "assessment_failed",
            "F",
            "不通过",
        )

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
                execution_completed=True,
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

    def test_authentication_failure_is_an_assessment_fail(self) -> None:
        model = self._model(
            check_authentication=lambda: AuthResult(
                AuthStatus.UNAUTHENTICATED,
                "login required",
            )
        )

        with pytest.raises(AssessmentOutcomeSignal, match="不通过") as outcome:
            AgentTestCase().assert_agent_authenticated(model, self._request())

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert "认证失败" in outcome.value.verdict.reason

    def test_incomplete_cli_turn_is_an_assessment_fail(self) -> None:
        turn = TurnResult("", "partial output", "timeout", 1, False, 5.0)

        with pytest.raises(AssessmentOutcomeSignal, match="不通过") as outcome:
            AgentTestCase().assert_turn_completed(
                turn,
                self._request(),
                self._model(),
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert "测试刺激未完成" in outcome.value.verdict.reason

    def test_missing_required_environment_configuration_is_an_assessment_fail(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("AGENT_TEST_REQUIRED_VALUE", raising=False)

        with pytest.raises(AssessmentOutcomeSignal, match="不通过") as outcome:
            AgentTestCase().require_environment_setting(
                "AGENT_TEST_REQUIRED_VALUE",
                self._request(),
                self._model(),
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert "AGENT_TEST_REQUIRED_VALUE" in outcome.value.verdict.reason

    def test_missing_required_judge_configuration_is_an_assessment_fail(self) -> None:
        with pytest.raises(AssessmentOutcomeSignal, match="不通过") as outcome:
            AgentTestCase().require_judge_model(
                None,
                self._request(),
                self._model(),
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert "Judge API" in outcome.value.verdict.reason

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
                execution_completed=True,
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

    @pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
    def test_unhandled_public_e2e_failure_is_reported_as_assessment_fail(
        self,
        phase: str,
    ) -> None:
        item = SimpleNamespace(
            path=Path(__file__).resolve().parents[1] / "test_cases" / "test_probe.py",
            keywords={"e2e": True},
            user_properties=[(ASSESSMENT_STATUS_PROPERTY, AssessmentStatus.PASS.value)],
            stash=pytest.Stash(),
        )
        report = SimpleNamespace(
            when=phase,
            outcome="failed",
            duration=0.1,
            longrepr="original traceback",
            user_properties=list(item.user_properties),
        )
        call = SimpleNamespace(excinfo=SimpleNamespace(value=RuntimeError("secret details")))

        hook = pytest_runtest_makereport(item, call)
        next(hook)
        with pytest.raises(StopIteration):
            hook.send(SimpleNamespace(get_result=lambda: report))

        properties = dict(report.user_properties)
        assert properties[ASSESSMENT_STATUS_PROPERTY] == AssessmentStatus.FAIL.value
        assert "RuntimeError" in properties["assessment_reason"]
        assert "secret details" not in properties["assessment_reason"]
        assert report.outcome == "failed"
        assert report.longrepr == "original traceback"
        assert dict(item.user_properties)[ASSESSMENT_STATUS_PROPERTY] == AssessmentStatus.FAIL.value

    def test_unhandled_offline_failure_keeps_existing_pytest_semantics(self) -> None:
        item = SimpleNamespace(
            path=Path(__file__),
            keywords={},
            user_properties=[],
            stash=pytest.Stash(),
        )
        report = SimpleNamespace(
            when="call",
            outcome="failed",
            duration=0.1,
            longrepr="offline traceback",
            user_properties=[],
        )
        call = SimpleNamespace(excinfo=SimpleNamespace(value=AssertionError("offline")))

        hook = pytest_runtest_makereport(item, call)
        next(hook)
        with pytest.raises(StopIteration):
            hook.send(SimpleNamespace(get_result=lambda: report))

        assert report.user_properties == []
        assert report.outcome == "failed"
        assert report.longrepr == "offline traceback"

    @staticmethod
    def _request() -> SimpleNamespace:
        return SimpleNamespace(node=SimpleNamespace(user_properties=[]))

    @staticmethod
    def _model(**attributes: object) -> SimpleNamespace:
        ledger = SimpleNamespace(record=lambda *_args: None)
        return SimpleNamespace(
            environment=SimpleNamespace(ledger=ledger),
            **attributes,
        )
