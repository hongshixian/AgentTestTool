"""Verify smoke-gated ReportLab PDF report generation."""

from datetime import datetime, timezone
from pathlib import Path

from assertions.outcome import AssessmentStatus
from reportlab.platypus import LongTable, Paragraph, Table

from agent_test_tool.reporting import (
    CaseCategory,
    CaseResult,
    ClauseDefinition,
    PDFReportGenerator,
    ReportData,
    RunMetadata,
    calculate_statistics,
    group_results_by_clause,
    load_clause_definitions,
)


TEST_CLAUSES = (
    ClauseDefinition(
        key="5.1a",
        security_domain="基础安全",
        standard_clause="5.1 a)",
        title="实例唯一身份标识与安全责任主体关联",
        original_text="智能体应用实例应具备唯一身份标识。",
    ),
    ClauseDefinition(
        key="6.1b",
        security_domain="交互安全",
        standard_clause="6.1 b)",
        title="输入安全检测与防护能力",
        original_text="智能体应用应对输入内容进行安全检测与防护。",
    ),
)


def _case(
    case_id: str,
    status: AssessmentStatus,
    category: CaseCategory,
    *,
    case_level: str = "",
    source_case_id: str = "",
    representative_child_id: str = "",
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        name=f"{case_id} 名称",
        status=status,
        reason=f"{case_id} 结果说明",
        category=category,
        duration_seconds=0.25,
        case_level=case_level,
        source_case_id=source_case_id,
        representative_child_id=representative_child_id,
    )


def _report(
    *,
    smoke_status: AssessmentStatus,
    business_results: tuple[CaseResult, ...] = (),
    case_suite: str = "",
) -> ReportData:
    return ReportData(
        metadata=RunMetadata(
            run_id="run-001",
            test_target="CodeBuddy Code CLI",
            generated_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
            case_suite=case_suite,
        ),
        smoke_results=(
            _case("SMOKE-001", smoke_status, CaseCategory.SMOKE),
        ),
        business_results=business_results,
    )


def _paragraph_text(story: list[object]) -> str:
    return "\n".join(
        item.getPlainText()
        for item in _walk_flowables(story)
        if isinstance(item, Paragraph)
    )


def _walk_flowables(items: list[object]) -> list[object]:
    flattened: list[object] = []
    for item in items:
        flattened.append(item)
        content = getattr(item, "_content", None)
        if isinstance(content, list):
            flattened.extend(_walk_flowables(content))
    return flattened


def _table_text(table: Table) -> list[list[str]]:
    return [
        [
            cell.getPlainText() if isinstance(cell, Paragraph) else str(cell)
            for cell in row
        ]
        for row in table._cellvalues
    ]


def _generator() -> PDFReportGenerator:
    return PDFReportGenerator(clauses=TEST_CLAUSES)


class TestPDFReporting:
    def test_generate_creates_a_nonempty_pdf(self, tmp_path: Path) -> None:
        report = _report(smoke_status=AssessmentStatus.FAIL)

        output = _generator().generate(report, tmp_path / "nested" / "report.pdf")

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

        text = _paragraph_text(_generator().build_story(report))

        assert "测试报告" in text
        assert "一、冒烟测试结果" in text
        assert "二、整体测试结果" not in text
        assert "三、条款级测试结果" not in text
        assert "四、各部分用例明细" not in text
        assert "业务测试未执行" in text

    def test_passing_smoke_uses_the_new_four_chapter_structure(
        self,
        tmp_path: Path,
    ) -> None:
        business = (
            _case(
                "ATS-5.1a-D1-01-S01-01",
                AssessmentStatus.PASS,
                CaseCategory.BUSINESS,
            ),
            _case(
                "ATS-5.1a-D1-01-S01-02",
                AssessmentStatus.FAIL,
                CaseCategory.BUSINESS,
            ),
            _case(
                "ATS-6.1b-D1-01-S01-01",
                AssessmentStatus.NOT_APPLICABLE,
                CaseCategory.BUSINESS,
            ),
            _case(
                "ATS-6.1b-D1-01-S01-02",
                AssessmentStatus.INCONCLUSIVE,
                CaseCategory.BUSINESS,
            ),
        )
        generator = _generator()

        story = generator.build_story(
            _report(smoke_status=AssessmentStatus.PASS, business_results=business)
        )
        text = _paragraph_text(story)

        assert "二、整体测试结果" in text
        assert "三、条款级测试结果" in text
        assert "3.1 基础安全-5.1 a)" in text
        assert "3.2 交互安全-6.1 b)" in text
        assert "四、各部分用例明细" in text
        assert "4.1 基础安全-5.1 a)" in text
        assert "4.2 交互安全-6.1 b)" in text
        assert "2.1 四态结果分布" not in text
        assert "2.2 用例明细" not in text
        long_tables = [
            item for item in _walk_flowables(story) if isinstance(item, LongTable)
        ]
        assert len(long_tables) == 3
        assert long_tables[-1].repeatRows == 1
        assert len(long_tables[1]._cellvalues) == 3
        assert len(long_tables[2]._cellvalues) == 3
        assert "代表路径" not in _table_text(long_tables[-1])[0]

        tables = [item for item in _walk_flowables(story) if type(item) is Table]
        clause_tables = [
            item
            for item in tables
            if _table_text(item)[0]
            == ["安全域", "国标章条", "条款标题", "条款原文"]
        ]
        assert len(clause_tables) == 2
        assert _table_text(clause_tables[0])[1] == [
            "基础安全",
            "5.1 a)",
            "实例唯一身份标识与安全责任主体关联",
            "智能体应用实例应具备唯一身份标识。",
        ]
        output = generator.generate(
            _report(smoke_status=AssessmentStatus.PASS, business_results=business),
            tmp_path / "complete-report.pdf",
        )
        assert output.read_bytes().startswith(b"%PDF-")

    def test_all_suite_combines_results_and_retains_representative_path(
        self,
        tmp_path: Path,
    ) -> None:
        mother = _case(
            "TC-6.1b-D5-01",
            AssessmentStatus.PASS,
            CaseCategory.BUSINESS,
            case_level="mother",
            representative_child_id="ATS-6.1b-D5-01-S01-01",
        )
        child = _case(
            "ATS-6.1b-D5-01-S01-02",
            AssessmentStatus.FAIL,
            CaseCategory.BUSINESS,
            case_level="child",
        )

        story = PDFReportGenerator(clauses=(TEST_CLAUSES[1],)).build_story(
            _report(
                smoke_status=AssessmentStatus.PASS,
                business_results=(mother, child),
                case_suite="all",
            )
        )
        text = _paragraph_text(story)

        assert "二、整体测试结果" in text
        assert "母用例代表路径" not in text
        assert "子用例展开路径" not in text
        detail_tables = [
            item for item in _walk_flowables(story) if isinstance(item, LongTable)
        ]
        assert len(detail_tables) == 2
        details = _table_text(detail_tables[1])
        assert details[0] == [
            "用例 ID",
            "用例名称",
            "代表路径",
            "结果",
            "简短说明",
        ]
        assert details[1][2] == "ATS-6.1b-D5-01-S01-01"
        assert details[2][2] == "—"

        statistic_tables = [
            item
            for item in _walk_flowables(story)
            if type(item) is Table and _table_text(item)[0][0] == "测评结果"
        ]
        assert len(statistic_tables) == 2
        overall_statistics = _table_text(statistic_tables[0])
        clause_statistics = _table_text(statistic_tables[1])
        assert overall_statistics[1][1] == "1"
        assert overall_statistics[2][1] == "1"
        assert clause_statistics[1][1] == "1"
        assert clause_statistics[2][1] == "1"
        output = PDFReportGenerator(clauses=(TEST_CLAUSES[1],)).generate(
            _report(
                smoke_status=AssessmentStatus.PASS,
                business_results=(mother, child),
                case_suite="all",
            ),
            tmp_path / "all-suite-report.pdf",
        )
        assert output.read_bytes().startswith(b"%PDF-")

    def test_mother_suite_keeps_one_compact_section_and_shows_representative_path(
        self,
    ) -> None:
        mother = _case(
            "TC-6.1b-D5-01",
            AssessmentStatus.PASS,
            CaseCategory.BUSINESS,
            case_level="mother",
            representative_child_id="ATS-6.1b-D5-01-S01-01",
        )

        story = PDFReportGenerator(clauses=(TEST_CLAUSES[1],)).build_story(
            _report(
                smoke_status=AssessmentStatus.PASS,
                business_results=(mother,),
                case_suite="mother",
            )
        )
        text = _paragraph_text(story)

        assert "二、整体测试结果" in text
        assert "母用例代表路径" not in text
        detail_tables = [
            item for item in _walk_flowables(story) if isinstance(item, LongTable)
        ]
        assert len(detail_tables) == 2
        mother_table = _table_text(detail_tables[-1])
        assert mother_table[0] == [
            "用例 ID",
            "用例名称",
            "代表路径",
            "结果",
            "简短说明",
        ]
        assert mother_table[1][2] == "ATS-6.1b-D5-01-S01-01"

    def test_clause_metadata_matches_the_frozen_workbook_overview(self) -> None:
        clauses = load_clause_definitions()

        assert len(clauses) == 50
        assert (
            clauses[0].security_domain,
            clauses[0].standard_clause,
            clauses[0].title,
            clauses[0].original_text,
        ) == (
            "基础安全",
            "5.1 a)",
            "实例唯一身份标识与安全责任主体关联",
            "智能体应用实例应具备唯一身份标识，该身份标识可用于识别、关联智能体应用安全责任主体。",
        )
        assert clauses[-1].section_title == "运行安全-7.2 c)"

    def test_clause_grouping_uses_source_id_and_keeps_unmatched_cases(self) -> None:
        first = _case(
            "CUSTOM-CASE",
            AssessmentStatus.PASS,
            CaseCategory.BUSINESS,
            source_case_id="TC-6.1b-D5-01",
        )
        second = _case(
            "ATS-5.1a-D2-01-S01-01",
            AssessmentStatus.FAIL,
            CaseCategory.BUSINESS,
        )
        unmatched = _case(
            "LEGACY-SEMANTIC-ID",
            AssessmentStatus.INCONCLUSIVE,
            CaseCategory.BUSINESS,
        )

        groups = group_results_by_clause(
            (first, second, unmatched),
            TEST_CLAUSES,
        )

        assert [group.section_title for group in groups] == [
            "基础安全-5.1 a)",
            "交互安全-6.1 b)",
            "未匹配条款-未匹配条款",
        ]
        assert groups[0].results == (second,)
        assert groups[1].results == (first,)
        assert groups[2].results == (unmatched,)

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
        generator = _generator()

        story = generator.build_story(report)
        detail_tables = [
            item for item in _walk_flowables(story) if isinstance(item, LongTable)
        ]
        assert _table_text(detail_tables[1])[1][1] == "该条款没有测试结果"

        output = generator.generate(report, tmp_path / "empty-business.pdf")

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
            _generator().build_story(report)
        )
