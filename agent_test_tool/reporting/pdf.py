"""Generate a self-contained PDF assessment report with ReportLab."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable

from assertions.outcome import AssessmentStatus
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Circle, Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .clauses import (
    ClauseDefinition,
    ClauseResultGroup,
    group_results_by_clause,
    load_clause_definitions,
)
from .models import CaseResult, ReportData
from .statistics import OutcomeStatistic, calculate_statistics


_STATUS_COLORS = {
    AssessmentStatus.PASS: colors.HexColor("#389E0D"),
    AssessmentStatus.FAIL: colors.HexColor("#CF1322"),
    AssessmentStatus.NOT_APPLICABLE: colors.HexColor("#8C8C8C"),
    AssessmentStatus.INCONCLUSIVE: colors.HexColor("#D46B08"),
}


@dataclass(frozen=True, slots=True)
class ReportFonts:
    """Registered font names available to the PDF renderer."""

    regular: str
    bold: str
    latin: str
    latin_bold: str


class PDFReportGenerator:
    """Render report data into an A4 PDF without an external document engine."""

    def __init__(
        self,
        *,
        regular_font_path: Path | None = None,
        bold_font_path: Path | None = None,
        clauses: Iterable[ClauseDefinition] | None = None,
    ) -> None:
        self.fonts = _register_fonts(regular_font_path, bold_font_path)
        self.styles = _styles(self.fonts)
        self.clauses = (
            tuple(clauses) if clauses is not None else load_clause_definitions()
        )

    def generate(self, report: ReportData, output_path: Path) -> Path:
        """Generate a complete PDF and return its resolved path."""
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=14 * mm,
            leftMargin=14 * mm,
            topMargin=20 * mm,
            bottomMargin=18 * mm,
            title="测试报告",
            author="AgentTestTool",
        )

        def decorate(canvas: object, _document: object) -> None:
            self._draw_header_footer(canvas, report)

        document.build(
            self.build_story(report),
            onFirstPage=decorate,
            onLaterPages=decorate,
        )
        return output_path

    def build_story(self, report: ReportData) -> list[Flowable]:
        """Build the smoke-gated four-chapter Platypus story."""
        story: list[Flowable] = []
        story.extend(self._cover(report))
        story.append(PageBreak())
        story.extend(self._smoke_section(report))
        if report.smoke_passed:
            story.append(PageBreak())
            story.extend(self._overall_section(report))
            story.append(PageBreak())
            story.extend(self._clause_results_section(report))
            story.append(PageBreak())
            story.extend(self._clause_details_section(report))
        return story

    def _cover(self, report: ReportData) -> list[Flowable]:
        generated_date = _date_text(report.metadata.generated_at)
        return [
            Spacer(1, 60 * mm),
            Paragraph("测试报告", self.styles["cover_title"]),
            Spacer(1, 24 * mm),
            Paragraph(
                "测试对象："
                + _mixed_safe(report.metadata.test_target, self.fonts.latin),
                self.styles["cover_detail"],
            ),
            Spacer(1, 8 * mm),
            Paragraph(
                "报告生成日期：" + _mixed_safe(generated_date, self.fonts.latin),
                self.styles["cover_detail"],
            ),
            Spacer(1, 8 * mm),
            Paragraph(
                "运行标识：" + _mixed_safe(report.metadata.run_id, self.fonts.latin),
                self.styles["cover_detail"],
            ),
        ]

    def _smoke_section(self, report: ReportData) -> list[Flowable]:
        passed = report.smoke_passed
        summary = "通过" if passed else "不通过"
        result_color = _STATUS_COLORS[
            AssessmentStatus.PASS if passed else AssessmentStatus.FAIL
        ]
        contents: list[Flowable] = [
            Paragraph("一、冒烟测试结果", self.styles["section"]),
            Paragraph(
                f'冒烟测试结论：<font color="{result_color.hexval()}"><b>{summary}</b></font>',
                self.styles["body"],
            ),
            Spacer(1, 4 * mm),
        ]
        if not report.smoke_results:
            contents.append(
                Paragraph("未取得冒烟测试结果，业务测试未执行。", self.styles["body"])
            )
            return contents
        contents.append(self._case_table(report.smoke_results, compact=False))
        if not passed:
            contents.extend(
                [
                    Spacer(1, 4 * mm),
                    Paragraph(
                        "冒烟测试未全部通过，当前不具备开展业务测试的条件，业务测试未执行。",
                        self.styles["notice"],
                    ),
                ]
            )
        return contents

    def _overall_section(self, report: ReportData) -> list[Flowable]:
        statistics = calculate_statistics(report.business_results)
        return [
            Paragraph("二、整体测试结果", self.styles["section"]),
            KeepTogether([self._pie_chart(statistics), Spacer(1, 3 * mm)]),
            self._statistics_table(statistics),
        ]

    def _clause_results_section(self, report: ReportData) -> list[Flowable]:
        contents: list[Flowable] = [
            Paragraph("三、条款级测试结果", self.styles["section"]),
        ]
        for index, group in enumerate(self._clause_groups(report), start=1):
            statistics = calculate_statistics(group.results)
            clause_contents: list[Flowable] = [
                Paragraph(
                    _mixed_safe(
                        f"3.{index} {group.section_title}",
                        self.fonts.latin_bold,
                    ),
                    self.styles["subsection"],
                ),
                self._clause_information_table(group),
                Spacer(1, 3 * mm),
                self._pie_chart(
                    statistics,
                    empty_message="该条款没有测试结果",
                ),
                Spacer(1, 3 * mm),
                self._statistics_table(statistics),
            ]
            contents.extend(
                [
                    KeepTogether(clause_contents),
                    Spacer(1, 7 * mm),
                ]
            )
        return contents

    def _clause_details_section(self, report: ReportData) -> list[Flowable]:
        contents: list[Flowable] = [
            Paragraph("四、各部分用例明细", self.styles["section"]),
        ]
        include_representative_path = bool(report.mother_results)
        for index, group in enumerate(self._clause_groups(report), start=1):
            contents.extend(
                [
                    Paragraph(
                        _mixed_safe(
                            f"4.{index} {group.section_title}",
                            self.fonts.latin_bold,
                        ),
                        self.styles["subsection"],
                    ),
                    self._case_table(
                        group.results,
                        compact=True,
                        include_representative_path=include_representative_path,
                        empty_message="该条款没有测试结果",
                    ),
                    Spacer(1, 7 * mm),
                ]
            )
        return contents

    def _clause_groups(self, report: ReportData) -> tuple[ClauseResultGroup, ...]:
        return group_results_by_clause(report.business_results, self.clauses)

    def _clause_information_table(self, group: ClauseResultGroup) -> Table:
        clause = group.clause
        values = (
            (
                clause.security_domain,
                clause.standard_clause,
                clause.title,
                clause.original_text,
            )
            if clause is not None
            else ("未匹配条款", "—", "无法从用例 ID 识别来源条款", "—")
        )
        rows: list[list[object]] = [
            [
                self._header_cell(value, compact=True)
                for value in ("安全域", "国标章条", "条款标题", "条款原文")
            ],
            [self._cell(value, compact=True) for value in values],
        ]
        table = Table(
            rows,
            colWidths=[25 * mm, 25 * mm, 50 * mm, 82 * mm],
            repeatRows=1,
        )
        table.setStyle(self._table_style(font_size=7))
        return table

    def _pie_chart(
        self,
        statistics: tuple[OutcomeStatistic, ...],
        *,
        empty_message: str = "本次没有业务测试结果",
    ) -> Drawing:
        drawing = Drawing(470, 185)
        values = [item.count for item in statistics]
        if not sum(values):
            drawing.add(
                Circle(
                    92.5,
                    92.5,
                    62.5,
                    fillColor=colors.HexColor("#F0F0F0"),
                    strokeColor=colors.HexColor("#BFBFBF"),
                )
            )
            drawing.add(
                String(
                    245,
                    89,
                    empty_message,
                    fontName=self.fonts.regular,
                    fontSize=10,
                )
            )
            return drawing
        pie = Pie()
        pie.x = 30
        pie.y = 30
        pie.width = 125
        pie.height = 125
        pie.data = values
        pie.labels = [
            _fullwidth_ascii(f"{item.status.value} {item.percentage:.1f}%")
            if item.count
            else ""
            for item in statistics
        ]
        pie.slices.fontName = self.fonts.regular
        pie.slices.fontSize = 7
        pie.slices.strokeColor = colors.white
        for index, item in enumerate(statistics):
            pie.slices[index].fillColor = _STATUS_COLORS[item.status]
        drawing.add(pie)
        for index, item in enumerate(statistics):
            y = 140 - index * 29
            drawing.add(Rect(245, y, 12, 12, fillColor=_STATUS_COLORS[item.status], strokeColor=None))
            drawing.add(
                String(
                    264,
                    y + 1,
                    _fullwidth_ascii(
                        f"{item.status.value}：{item.count} 条（{item.percentage:.2f}%）"
                    ),
                    fontName=self.fonts.regular,
                    fontSize=9,
                )
            )
        return drawing

    def _statistics_table(
        self, statistics: tuple[OutcomeStatistic, ...]
    ) -> Table:
        rows: list[list[object]] = [
            [
                self._header_cell(value, compact=False)
                for value in ("测评结果", "用例数量", "占比")
            ]
        ]
        rows.extend(
            [item.status.value, str(item.count), f"{item.percentage:.2f}%"]
            for item in statistics
        )
        table = Table(rows, colWidths=[75 * mm, 45 * mm, 45 * mm], repeatRows=1)
        table.setStyle(self._table_style(font_size=9))
        table.setStyle(
            TableStyle(
                [("FONTNAME", (1, 1), (-1, -1), self.fonts.latin)]
            )
        )
        return table

    def _case_table(
        self,
        results: Iterable[CaseResult],
        *,
        compact: bool,
        include_representative_path: bool = False,
        empty_message: str = "本次没有业务测试结果",
    ) -> LongTable:
        if include_representative_path:
            rows: list[list[object]] = [
                [
                    self._header_cell(value, compact=compact)
                    for value in (
                        "用例 ID",
                        "用例名称",
                        "代表路径",
                        "结果",
                        "简短说明",
                    )
                ]
            ]
            rows.extend(
                [
                    self._cell(item.case_id, compact=compact),
                    self._cell(item.name, compact=compact),
                    self._cell(
                        item.representative_child_id or "—",
                        compact=compact,
                    ),
                    self._cell(item.status.value, compact=compact),
                    self._cell(item.reason, compact=compact),
                ]
                for item in results
            )
            column_widths = [32 * mm, 37 * mm, 43 * mm, 18 * mm, 52 * mm]
        else:
            rows = [
                [
                    self._header_cell(value, compact=compact)
                    for value in ("用例 ID", "用例名称", "结果", "简短说明")
                ]
            ]
            rows.extend(
                [
                    self._cell(item.case_id, compact=compact),
                    self._cell(item.name, compact=compact),
                    self._cell(item.status.value, compact=compact),
                    self._cell(item.reason, compact=compact),
                ]
                for item in results
            )
            column_widths = [44 * mm, 48 * mm, 19 * mm, 71 * mm]
        if len(rows) == 1:
            empty_row = [
                self._cell("—", compact=compact),
                self._cell(empty_message, compact=compact),
            ]
            if include_representative_path:
                empty_row.append(self._cell("—", compact=compact))
            empty_row.extend(
                [
                    self._cell("—", compact=compact),
                    self._cell("—", compact=compact),
                ]
            )
            rows.append(empty_row)
        table = LongTable(
            rows,
            colWidths=column_widths,
            repeatRows=1,
            splitByRow=1,
        )
        table.setStyle(self._table_style(font_size=6.5 if compact else 8))
        return table

    def _cell(self, value: str, *, compact: bool) -> Paragraph:
        style = self.styles["table_compact" if compact else "table"]
        return Paragraph(_mixed_safe(value, self.fonts.latin), style)

    def _header_cell(self, value: str, *, compact: bool) -> Paragraph:
        style = self.styles[
            "table_header_compact" if compact else "table_header"
        ]
        return Paragraph(_mixed_safe(value, self.fonts.latin_bold), style)

    def _table_style(self, *, font_size: float) -> TableStyle:
        return TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), self.fonts.bold),
                ("FONTNAME", (0, 1), (-1, -1), self.fonts.regular),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F4FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#102A43")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#BFBFBF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )

    def _draw_header_footer(self, canvas: object, report: ReportData) -> None:
        canvas.saveState()
        canvas.setFont(self.fonts.regular, 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(
            14 * mm,
            A4[1] - 10 * mm,
            _fullwidth_ascii("AgentTestTool 测试报告"),
        )
        canvas.drawRightString(
            A4[0] - 14 * mm,
            A4[1] - 10 * mm,
            _fullwidth_ascii(report.metadata.test_target),
        )
        canvas.line(14 * mm, A4[1] - 12 * mm, A4[0] - 14 * mm, A4[1] - 12 * mm)
        canvas.line(14 * mm, 12 * mm, A4[0] - 14 * mm, 12 * mm)
        canvas.drawString(
            14 * mm,
            8 * mm,
            _fullwidth_ascii(f"RUN_ID：{report.metadata.run_id}"),
        )
        canvas.drawRightString(
            A4[0] - 14 * mm,
            8 * mm,
            _fullwidth_ascii(f"第 {canvas.getPageNumber()} 页"),
        )
        canvas.restoreState()


def generate_pdf(
    report: ReportData,
    output_path: Path,
    *,
    regular_font_path: Path | None = None,
    bold_font_path: Path | None = None,
) -> Path:
    """Convenience entry point for direct ReportLab PDF generation."""
    return PDFReportGenerator(
        regular_font_path=regular_font_path,
        bold_font_path=bold_font_path,
    ).generate(report, output_path)


def _styles(fonts: ReportFonts) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "ReportCoverTitle",
            parent=sample["Title"],
            fontName=fonts.bold,
            fontSize=34,
            leading=44,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#102A43"),
        ),
        "cover_detail": ParagraphStyle(
            "ReportCoverDetail",
            parent=sample["Normal"],
            fontName=fonts.regular,
            fontSize=13,
            leading=20,
            alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "ReportSection",
            parent=sample["Heading1"],
            fontName=fonts.bold,
            fontSize=18,
            leading=25,
            spaceAfter=7 * mm,
            textColor=colors.HexColor("#102A43"),
        ),
        "subsection": ParagraphStyle(
            "ReportSubsection",
            parent=sample["Heading2"],
            fontName=fonts.bold,
            fontSize=12,
            leading=18,
            spaceBefore=3 * mm,
            spaceAfter=3 * mm,
            keepWithNext=1,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=sample["BodyText"],
            fontName=fonts.regular,
            fontSize=10,
            leading=16,
            alignment=TA_LEFT,
        ),
        "notice": ParagraphStyle(
            "ReportNotice",
            parent=sample["BodyText"],
            fontName=fonts.bold,
            fontSize=10,
            leading=16,
            textColor=colors.HexColor("#CF1322"),
        ),
        "table": ParagraphStyle(
            "ReportTableCell",
            parent=sample["BodyText"],
            fontName=fonts.regular,
            fontSize=8,
            leading=11,
        ),
        "table_compact": ParagraphStyle(
            "ReportCompactTableCell",
            parent=sample["BodyText"],
            fontName=fonts.regular,
            fontSize=6.5,
            leading=8.5,
        ),
        "table_header": ParagraphStyle(
            "ReportTableHeaderCell",
            parent=sample["BodyText"],
            fontName=fonts.bold,
            fontSize=8,
            leading=11,
        ),
        "table_header_compact": ParagraphStyle(
            "ReportCompactTableHeaderCell",
            parent=sample["BodyText"],
            fontName=fonts.bold,
            fontSize=6.5,
            leading=8.5,
        ),
    }


def _register_fonts(
    regular_font_path: Path | None,
    bold_font_path: Path | None,
) -> ReportFonts:
    regular_candidate = regular_font_path or _first_existing_font(
        (
            Path("assets/fonts/report_regular.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
            Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("/System/Library/Fonts/PingFang.ttc"),
        )
    )
    bold_candidate = bold_font_path or _first_existing_font(
        (
            Path("assets/fonts/report_bold.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
            Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
            Path("C:/Windows/Fonts/msyhbd.ttc"),
            Path("/System/Library/Fonts/PingFang.ttc"),
        )
    )
    if regular_candidate is not None:
        regular_name = "AgentTestReportRegular"
        pdfmetrics.registerFont(TTFont(regular_name, str(regular_candidate)))
        if bold_candidate is not None:
            bold_name = "AgentTestReportBold"
            pdfmetrics.registerFont(TTFont(bold_name, str(bold_candidate)))
        else:
            bold_name = regular_name
        return ReportFonts(regular_name, bold_name, "Helvetica", "Helvetica-Bold")

    fallback = "STSong-Light"
    if fallback not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    return ReportFonts(fallback, fallback, "Helvetica", "Helvetica-Bold")


def _first_existing_font(candidates: Iterable[Path]) -> Path | None:
    return next((path.resolve() for path in candidates if path.is_file()), None)


_ASCII_RUN_PATTERN = re.compile(r"[\x20-\x7e]+")


def _mixed_safe(value: object, latin_font: str) -> str:
    """Escape text and render ASCII runs with a font that contains Latin glyphs."""
    lines: list[str] = []
    for line in str(value).split("\n"):
        position = 0
        parts: list[str] = []
        for match in _ASCII_RUN_PATTERN.finditer(line):
            parts.append(escape(line[position : match.start()], quote=True))
            parts.append(
                f'<font name="{latin_font}">'
                f"{escape(match.group(), quote=True)}"
                "</font>"
            )
            position = match.end()
        parts.append(escape(line[position:], quote=True))
        lines.append("".join(parts))
    return "<br/>".join(lines)


def _fullwidth_ascii(value: object) -> str:
    """Map printable ASCII to CJK fullwidth glyphs for canvas and chart labels."""
    return "".join(
        chr(ord(character) + 0xFEE0)
        if "!" <= character <= "~"
        else character
        for character in str(value)
    )


def _date_text(value: datetime) -> str:
    return value.astimezone().strftime("%Y年%m月%d日")
