"""Clause metadata and business-case grouping for assessment reports."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .models import CaseResult


_CASE_CLAUSE_PATTERN = re.compile(
    r"^(?:ATS|TC)-(?P<clause>\d+(?:\.\d+)+[A-Za-z]?)(?:-|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ClauseDefinition:
    """One reportable standard clause from the source workbook."""

    key: str
    security_domain: str
    standard_clause: str
    title: str
    original_text: str

    @property
    def section_title(self) -> str:
        """Return the subsection title requested by the report specification."""
        return f"{self.security_domain}-{self.standard_clause}"


@dataclass(frozen=True, slots=True)
class ClauseResultGroup:
    """Cases assigned to one clause, or to the unmatched fallback group."""

    clause: ClauseDefinition | None
    results: tuple[CaseResult, ...]

    @property
    def section_title(self) -> str:
        """Return a stable display title for this group."""
        if self.clause is None:
            return "未匹配条款-未匹配条款"
        return self.clause.section_title


@lru_cache(maxsize=1)
def load_clause_definitions() -> tuple[ClauseDefinition, ...]:
    """Load the frozen clause overview exported from the source workbook."""
    path = Path(__file__).with_name("clauses.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("条款元数据顶层必须是对象")
    raw_clauses = payload.get("clauses")
    if not isinstance(raw_clauses, Sequence) or isinstance(raw_clauses, str):
        raise ValueError("条款元数据缺少 clauses 数组")

    clauses: list[ClauseDefinition] = []
    seen_keys: set[str] = set()
    for item in raw_clauses:
        if not isinstance(item, Mapping):
            raise ValueError("条款元数据项必须是对象")
        clause = ClauseDefinition(
            key=_required_text(item, "key"),
            security_domain=_required_text(item, "security_domain"),
            standard_clause=_required_text(item, "standard_clause"),
            title=_required_text(item, "title"),
            original_text=_required_text(item, "original_text"),
        )
        if clause.key in seen_keys:
            raise ValueError(f"条款元数据包含重复编号：{clause.key}")
        seen_keys.add(clause.key)
        clauses.append(clause)
    if not clauses:
        raise ValueError("条款元数据不能为空")
    return tuple(clauses)


def clause_key_from_case(case: CaseResult) -> str | None:
    """Extract a normalized standard-clause key from one business result."""
    for candidate in (case.source_case_id, case.case_id):
        match = _CASE_CLAUSE_PATTERN.match(candidate.strip())
        if match:
            return match.group("clause").casefold()
    return None


def group_results_by_clause(
    results: Iterable[CaseResult],
    clauses: Iterable[ClauseDefinition] | None = None,
) -> tuple[ClauseResultGroup, ...]:
    """Group cases in workbook order and append an unmatched group when needed."""
    definitions = tuple(clauses) if clauses is not None else load_clause_definitions()
    buckets: dict[str, list[CaseResult]] = {clause.key: [] for clause in definitions}
    unmatched: list[CaseResult] = []
    for result in results:
        key = clause_key_from_case(result)
        if key is None or key not in buckets:
            unmatched.append(result)
        else:
            buckets[key].append(result)
    groups = [
        ClauseResultGroup(clause=clause, results=tuple(buckets[clause.key]))
        for clause in definitions
    ]
    if unmatched:
        groups.append(ClauseResultGroup(clause=None, results=tuple(unmatched)))
    return tuple(groups)


def _required_text(payload: Mapping[object, object], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"条款元数据字段不能为空：{key}")
    return value
