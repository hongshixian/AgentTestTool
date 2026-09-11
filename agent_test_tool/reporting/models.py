"""Structured data models used by assessment reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from assertions.outcome import AssessmentStatus


class CaseCategory(str, Enum):
    """Report section to which an assessment case belongs."""

    SMOKE = "smoke"
    BUSINESS = "business"


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Metadata shared by every section of a generated report."""

    run_id: str
    test_target: str
    generated_at: datetime
    schema_version: str = "1.0"
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float | None = None
    platform: str = ""
    agent_version: str = ""
    case_suite: str = ""

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        test_target: str | None = None,
    ) -> RunMetadata:
        """Build run metadata from a pytest result payload with safe defaults."""
        session = _mapping(payload.get("session"))
        metadata = _mapping(payload.get("metadata"))
        generated_value = (
            payload.get("generated_at")
            or metadata.get("generated_at")
            or session.get("finished_at")
            or session.get("finished")
        )
        return cls(
            run_id=_text(payload.get("run_id"), "unknown-run"),
            test_target=_text(
                test_target
                or payload.get("test_target")
                or payload.get("target")
                or metadata.get("test_target"),
                "未指定测试对象",
            ),
            generated_at=_datetime(generated_value),
            schema_version=_text(payload.get("schema_version"), "1.0"),
            started_at=_text(session.get("started_at") or session.get("started")),
            finished_at=_text(session.get("finished_at") or session.get("finished")),
            duration_seconds=_number_or_none(
                session.get("duration_seconds") or session.get("duration")
            ),
            platform=_text(payload.get("platform") or metadata.get("platform")),
            agent_version=_text(
                payload.get("agent_version") or metadata.get("agent_version")
            ),
            case_suite=_text(payload.get("case_suite") or metadata.get("case_suite")),
        )


@dataclass(frozen=True, slots=True)
class CaseResult:
    """One independently reported assessment case result."""

    case_id: str
    name: str
    status: AssessmentStatus
    reason: str
    category: CaseCategory
    duration_seconds: float | None = None
    missing_evidence: tuple[str, ...] = ()
    pytest_status: str = ""
    nodeid: str = ""
    phases: tuple[Mapping[str, Any], ...] = ()
    case_level: str = ""
    source_case_id: str = ""
    representative_child_id: str = ""

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        default_category: CaseCategory,
    ) -> CaseResult:
        """Normalize one case emitted by the pytest result collector."""
        nodeid = _text(payload.get("nodeid"))
        case_id = _text(payload.get("test_case_id"), nodeid or "UNKNOWN")
        pytest_status = _text(payload.get("pytest_status"))
        case_level = _case_level(_text(payload.get("case_level")), case_id)
        return cls(
            case_id=case_id,
            name=_text(payload.get("name"), case_id),
            status=_status(payload.get("status"), pytest_status=pytest_status),
            reason=_text(payload.get("reason"), "未提供结果说明"),
            category=_category(payload, default=default_category),
            duration_seconds=_number_or_none(payload.get("duration_seconds")),
            missing_evidence=tuple(
                _text(item)
                for item in _sequence(payload.get("missing_evidence"))
                if _text(item)
            ),
            pytest_status=pytest_status,
            nodeid=nodeid,
            phases=tuple(
                item for item in _sequence(payload.get("phases")) if isinstance(item, Mapping)
            ),
            case_level=case_level,
            source_case_id=_text(payload.get("source_case_id")),
            representative_child_id=_text(payload.get("representative_child_id")),
        )


@dataclass(frozen=True, slots=True)
class ReportData:
    """Complete input for a smoke-gated assessment report."""

    metadata: RunMetadata
    smoke_results: tuple[CaseResult, ...]
    business_results: tuple[CaseResult, ...] = field(default_factory=tuple)
    business_errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def smoke_passed(self) -> bool:
        """Return true only when at least one smoke case exists and all pass."""
        return bool(self.smoke_results) and all(
            case.status is AssessmentStatus.PASS for case in self.smoke_results
        )

    @property
    def mother_results(self) -> tuple[CaseResult, ...]:
        """Return only source workbook cases, including legacy TC-* payloads."""
        return tuple(
            case
            for case in self.business_results
            if _case_level(case.case_level, case.case_id) == "mother"
        )

    @property
    def child_results(self) -> tuple[CaseResult, ...]:
        """Return only expanded prompt cases, including legacy ATS-* payloads."""
        return tuple(
            case
            for case in self.business_results
            if _case_level(case.case_level, case.case_id) == "child"
        )

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        test_target: str | None = None,
    ) -> ReportData:
        """Build a report from either grouped cases or one flat result payload."""
        smoke_items = payload.get("smoke_cases")
        business_items = payload.get("business_cases")
        if smoke_items is None and business_items is None:
            cases = _case_mappings(payload.get("cases"))
            normalized = tuple(
                CaseResult.from_mapping(item, default_category=CaseCategory.BUSINESS)
                for item in cases
            )
            smoke = tuple(
                case for case in normalized if case.category is CaseCategory.SMOKE
            )
            business = tuple(
                case for case in normalized if case.category is CaseCategory.BUSINESS
            )
        else:
            smoke = tuple(
                CaseResult.from_mapping(item, default_category=CaseCategory.SMOKE)
                for item in _case_mappings(smoke_items)
            )
            business = tuple(
                CaseResult.from_mapping(item, default_category=CaseCategory.BUSINESS)
                for item in _case_mappings(business_items)
            )
        return cls(
            metadata=RunMetadata.from_mapping(payload, test_target=test_target),
            smoke_results=smoke,
            business_results=business,
        )

    @classmethod
    def from_pytest_payloads(
        cls,
        smoke_payload: Mapping[str, Any],
        business_payload: Mapping[str, Any] | None = None,
        *,
        test_target: str | None = None,
    ) -> ReportData:
        """Combine the two pytest stages without relying on console output."""
        smoke = tuple(
            CaseResult.from_mapping(item, default_category=CaseCategory.SMOKE)
            for item in _case_mappings(smoke_payload.get("cases"))
        )
        business = (
            tuple(
                CaseResult.from_mapping(item, default_category=CaseCategory.BUSINESS)
                for item in _case_mappings(business_payload.get("cases"))
            )
            if business_payload is not None
            else ()
        )
        metadata_source = dict(smoke_payload)
        business_errors: list[str] = []
        if business_payload is not None:
            smoke_session = _mapping(smoke_payload.get("session"))
            business_session = _mapping(business_payload.get("session"))
            for field_name in ("internal_errors", "collection_errors"):
                messages = business_session.get(field_name)
                if isinstance(messages, list) and messages:
                    business_errors.extend(str(message) for message in messages if message)
            if business_payload.get("phase_error"):
                business_errors.append(str(business_payload["phase_error"]))
            if business_session.get("exitstatus") not in (None, 0) and not any(
                case.status is AssessmentStatus.FAIL for case in business
            ):
                business_errors.append("业务进程异常退出，已记录用例结果不能代表本次测评完整完成")
            metadata_source["session"] = {
                "started_at": smoke_session.get("started_at")
                or smoke_session.get("started", ""),
                "finished_at": business_session.get("finished_at")
                or business_session.get("finished", ""),
                "duration_seconds": _sum_durations(
                    smoke_session.get("duration_seconds")
                    or smoke_session.get("duration"),
                    business_session.get("duration_seconds")
                    or business_session.get("duration"),
                ),
            }
            metadata_source["case_suite"] = business_payload.get("case_suite", "")
        return cls(
            metadata=RunMetadata.from_mapping(
                metadata_source,
                test_target=test_target,
            ),
            smoke_results=smoke,
            business_results=business,
            business_errors=tuple(dict.fromkeys(business_errors)),
        )

    @classmethod
    def from_json(
        cls,
        path: Path,
        *,
        test_target: str | None = None,
    ) -> ReportData:
        """Read a UTF-8 JSON result file and normalize it for reporting."""
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("报告 JSON 顶层必须是对象")
        return cls.from_mapping(payload, test_target=test_target)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _case_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    return tuple(item for item in _sequence(value) if isinstance(item, Mapping))


def _case_level(value: str, case_id: str) -> str:
    normalized = value.strip().casefold()
    if normalized in {"mother", "child", "smoke"}:
        return normalized
    if case_id.startswith("TC-"):
        return "mother"
    if case_id.startswith("ATS-"):
        return "child"
    return normalized


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    normalized = str(value).strip()
    return normalized or default


def _number_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _status(value: Any, *, pytest_status: str) -> AssessmentStatus:
    if isinstance(value, AssessmentStatus):
        return value
    normalized = _text(value).casefold()
    aliases = {
        "通过": AssessmentStatus.PASS,
        "pass": AssessmentStatus.PASS,
        "passed": AssessmentStatus.PASS,
        "assessment_passed": AssessmentStatus.PASS,
        "不通过": AssessmentStatus.FAIL,
        "fail": AssessmentStatus.FAIL,
        "failed": AssessmentStatus.FAIL,
        "assessment_failed": AssessmentStatus.FAIL,
        "不适用": AssessmentStatus.NOT_APPLICABLE,
        "not_applicable": AssessmentStatus.NOT_APPLICABLE,
        "n/a": AssessmentStatus.NOT_APPLICABLE,
        "无法判定": AssessmentStatus.INCONCLUSIVE,
        "inconclusive": AssessmentStatus.INCONCLUSIVE,
    }
    if normalized in aliases:
        return aliases[normalized]
    if pytest_status.casefold() in {"failed", "error", "assessment_failed"}:
        return AssessmentStatus.FAIL
    return AssessmentStatus.INCONCLUSIVE


def _category(payload: Mapping[str, Any], *, default: CaseCategory) -> CaseCategory:
    if payload.get("is_smoke") is True:
        return CaseCategory.SMOKE
    value = _text(payload.get("category") or payload.get("suite")).casefold()
    markers = {_text(marker).casefold() for marker in _sequence(payload.get("markers"))}
    if value in {"smoke", "冒烟"} or "smoke" in markers:
        return CaseCategory.SMOKE
    if value in {"business", "业务"}:
        return CaseCategory.BUSINESS
    return default


def _sum_durations(*values: Any) -> float | None:
    durations = [value for item in values if (value := _number_or_none(item)) is not None]
    return sum(durations) if durations else None
