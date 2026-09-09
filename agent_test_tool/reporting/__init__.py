"""Public interfaces for structured PDF assessment reporting."""

from .models import CaseCategory, CaseResult, ReportData, RunMetadata
from .pdf import PDFReportGenerator, generate_pdf
from .statistics import OutcomeStatistic, calculate_statistics

__all__ = [
    "CaseCategory",
    "CaseResult",
    "OutcomeStatistic",
    "PDFReportGenerator",
    "ReportData",
    "RunMetadata",
    "calculate_statistics",
    "generate_pdf",
]
