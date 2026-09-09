"""Verify smoke-gated ReportLab PDF report generation."""

from datetime import datetime, timezone
from pathlib import Path

from assertions.outcome import AssessmentStatus
from reportlab.platypus import LongTable, Paragraph

from agent_test_tool.reporting import (
    CaseCategory,
    CaseResult,
    PDFReportGenerator,
    ReportData,
    RunMetadata,
    calculate_statistics,
)


def _case(
    case_id: str,
    status: AssessmentStatus,
    category: CaseCategory,
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        name=f"{case_id} 名称",
        status=status,
        reason=f"{case_id} 结果说明",
        category=category,
        duration_seconds=0.25,
    )


def _report(
    *,
    smoke_status: AssessmentStatus,
    business_results: tuple[CaseResult, ...] = (),
) -> ReportData:
    return ReportData(
        metadata=RunMetadata(
            run_id="run-001",
            test_target="CodeBuddy Code CLI",
            generated_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
        ),
        smoke_results=(
            _case("SMOKE-001", smoke_status, CaseCategory.SMOKE),
        ),
        business_results=business_results,
    )


def _paragraph_text(story: list[object]) -> str:
    return "\n".join(
        item.getPlainText() for item in story if isinstance(item, Paragraph)
    )


class TestPDFReporting:
    def test_generate_creates_a_nonempty_pdf(self, tmp_path: Path) -> None:
        report = _report(smoke_status=AssessmentStatus.FAIL)

        output = PDFReportGenerator().generate(report, tmp_path / "nested" / "report.pdf")

        assert output.is_file()
        assert output.read_bytes().startswith(b"%PDF-")
        assert output.stat().st_size > 1_000

    def test_failed_smoke_omits_the_business_section(self) -> None:
        report = _report(
            smoke_status=AssessmentStatus.FAIL,
            business_results=(
                _case("ATS-001", AssessmentStatus.PASS, CaseCategory.BUSINESS),
            ),
        )

        text = _paragraph_text(PDFReportGenerator().build_story(report))

        assert "测试报告" in text
        assert "一、冒烟测试结果" in text
        assert "二、业务测试结果" not in text
        assert "业务测试未执行" in text

    def test_passing_smoke_includes_chart_statistics_and_long_detail_table(
        self,
        tmp_path: Path,
    ) -> None:
        business = tuple(
            _case(f"ATS-{index:03d}", status, CaseCategory.BUSINESS)
            for index, status in enumerate(
                (
                    AssessmentStatus.PASS,
                    AssessmentStatus.FAIL,
                    AssessmentStatus.NOT_APPLICABLE,
                    AssessmentStatus.INCONCLUSIVE,
                ),
                start=1,
            )
        )
        generator = PDFReportGenerator()

        story = generator.build_story(
            _report(smoke_status=AssessmentStatus.PASS, business_results=business)
        )
        text = _paragraph_text(story)

        assert "二、业务测试结果" in text
        assert "2.1 四态结果分布" in text
        assert "2.2 用例明细" in text
        long_tables = [item for item in story if isinstance(item, LongTable)]
        assert len(long_tables) == 2
        assert long_tables[-1].repeatRows == 1
        assert len(long_tables[-1]._cellvalues) == 5
        output = generator.generate(
            _report(smoke_status=AssessmentStatus.PASS, business_results=business),
            tmp_path / "complete-report.pdf",
        )
        assert output.read_bytes().startswith(b"%PDF-")

    def test_statistics_always_include_all_four_outcomes(self) -> None:
        results = (
            _case("ATS-001", AssessmentStatus.PASS, CaseCategory.BUSINESS),
            _case("ATS-002", AssessmentStatus.PASS, CaseCategory.BUSINESS),
            _case("ATS-003", AssessmentStatus.FAIL, CaseCategory.BUSINESS),
            _case("ATS-004", AssessmentStatus.INCONCLUSIVE, CaseCategory.BUSINESS),
        )

        statistics = calculate_statistics(results)

        assert [(item.status, item.count) for item in statistics] == [
            (AssessmentStatus.PASS, 2),
            (AssessmentStatus.FAIL, 1),
            (AssessmentStatus.NOT_APPLICABLE, 0),
            (AssessmentStatus.INCONCLUSIVE, 1),
        ]
        assert [item.percentage for item in statistics] == [50.0, 25.0, 0.0, 25.0]
        assert sum(item.percentage for item in statistics) == 100.0

    def test_passing_smoke_with_no_business_results_still_generates(
        self,
        tmp_path: Path,
    ) -> None:
        report = _report(smoke_status=AssessmentStatus.PASS)

        output = PDFReportGenerator().generate(report, tmp_path / "empty-business.pdf")

        assert output.is_file()
        assert [item.count for item in calculate_statistics(())] == [0, 0, 0, 0]

    def test_pytest_payload_adapter_handles_missing_fields_and_stage_split(self) -> None:
        smoke_payload = {
            "schema_version": "1.0",
            "run_id": "run-adapter",
            "session": {"started": "2026-09-09T10:00:00+08:00", "duration": 1.5},
            "cases": [
                {
                    "nodeid": "test_cases/test_smoke.py::TestSmoke::test_cli",
                    "test_case_id": "SMOKE-CLI",
                    "status": "通过",
                    "pytest_status": "passed",
                }
            ],
        }
        business_payload = {
            "session": {"finished": "2026-09-09T10:00:03+08:00", "duration": 1.0},
            "cases": [
                {
                    "nodeid": "test_cases/test_business.py::TestBusiness::test_rule",
                    "test_case_id": "ATS-001",
                    "name": "业务规则",
                    "status": "mystery",
                    "pytest_status": "failed",
                    "phases": [{"when": "call", "outcome": "failed"}],
                }
            ],
        }

        report = ReportData.from_pytest_payloads(
            smoke_payload,
            business_payload,
            test_target="CodeBuddy Code CLI",
        )

        assert report.smoke_passed is True
        assert report.metadata.run_id == "run-adapter"
        assert report.metadata.duration_seconds == 2.5
        assert report.smoke_results[0].category is CaseCategory.SMOKE
        assert report.business_results[0].category is CaseCategory.BUSINESS
        assert report.business_results[0].status is AssessmentStatus.FAIL
        assert report.business_results[0].reason == "未提供结果说明"
        assert report.business_results[0].phases[0]["when"] == "call"

    def test_empty_smoke_stage_never_opens_the_business_gate(self) -> None:
        report = ReportData(
            metadata=RunMetadata(
                run_id="empty-smoke",
                test_target="CodeBuddy Code CLI",
                generated_at=datetime.now(timezone.utc),
            ),
            smoke_results=(),
            business_results=(
                _case("ATS-001", AssessmentStatus.PASS, CaseCategory.BUSINESS),
            ),
        )

        assert report.smoke_passed is False
        assert "二、业务测试结果" not in _paragraph_text(
            PDFReportGenerator().build_story(report)
        )
