"""Public interfaces for structured PDF assessment reporting."""

from .clauses import (
    ClauseDefinition,
    ClauseResultGroup,
    clause_key_from_case,
    group_results_by_clause,
    load_clause_definitions,
)
from .models import CaseCategory, CaseResult, ReportData, RunMetadata
from .pdf import PDFReportGenerator, generate_pdf
from .statistics import OutcomeStatistic, calculate_statistics

__all__ = [
    "CaseCategory",
    "CaseResult",
    "ClauseDefinition",
    "ClauseResultGroup",
    "OutcomeStatistic",
    "PDFReportGenerator",
    "ReportData",
    "RunMetadata",
    "calculate_statistics",
    "clause_key_from_case",
    "generate_pdf",
    "group_results_by_clause",
    "load_clause_definitions",
]
