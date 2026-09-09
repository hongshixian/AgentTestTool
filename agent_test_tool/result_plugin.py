"""Collect structured four-state assessment results from pytest runs."""

from __future__ import annotations

import inspect
import json
import os
import re
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import pytest


SCHEMA_VERSION = 1
ASSESSMENT_STATUS_PROPERTY = "assessment_status"
ASSESSMENT_REASON_PROPERTY = "assessment_reason"
ASSESSMENT_MISSING_EVIDENCE_PROPERTY = "assessment_missing_evidence"
ASSESSMENT_STATUSES = ("通过", "不通过", "不适用", "无法判定")
_TEST_NAME_PATTERN = re.compile(r"^\s*测试用例名称\s*[：:]\s*(.+?)\s*$", re.MULTILINE)
_TEST_ID_PATTERN = re.compile(r"^\s*测试用例\s*ID\s*[：:]\s*([^（\s]+)", re.MULTILINE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _properties(report: pytest.TestReport) -> dict[str, object]:
    return dict(getattr(report, "user_properties", ()))


def _normalize_missing_evidence(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[；;]", value) if part.strip()]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(part).strip() for part in value if str(part).strip()]
    normalized = str(value).strip()
    return [normalized] if normalized else []


def _raw_pytest_status(phases: dict[str, dict[str, object]]) -> str:
    if any(
        phase != "call" and values.get("outcome") == "failed"
        for phase, values in phases.items()
    ):
        return "error"
    if any(values.get("outcome") == "failed" for values in phases.values()):
        return "failed"
    if any(values.get("outcome") == "skipped" for values in phases.values()):
        return "skipped"
    if phases.get("call", {}).get("outcome") == "passed":
        return "passed"
    return "not_run"


def _exit_status_name(exit_status: int) -> str:
    names = {
        int(pytest.ExitCode.OK): "passed",
        int(pytest.ExitCode.TESTS_FAILED): "failed",
        int(pytest.ExitCode.INTERRUPTED): "interrupted",
        int(pytest.ExitCode.INTERNAL_ERROR): "internal_error",
        int(pytest.ExitCode.USAGE_ERROR): "usage_error",
        int(pytest.ExitCode.NO_TESTS_COLLECTED): "no_tests_collected",
    }
    return names.get(int(exit_status), "unknown")


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    """Write JSON through a sibling temporary file and atomically replace the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


@dataclass(slots=True)
class _CaseState:
    nodeid: str
    test_case_id: str
    name: str
    is_e2e: bool
    phases: dict[str, dict[str, object]] = field(default_factory=dict)

    def record(self, report: pytest.TestReport) -> None:
        properties = _properties(report)
        self.phases[report.when] = {
            "outcome": report.outcome,
            "duration_seconds": round(float(report.duration), 6),
            "assessment_status": properties.get(ASSESSMENT_STATUS_PROPERTY),
            "assessment_reason": properties.get(ASSESSMENT_REASON_PROPERTY),
            "assessment_missing_evidence": properties.get(
                ASSESSMENT_MISSING_EVIDENCE_PROPERTY
            ),
        }

    def serialize(self) -> dict[str, object]:
        raw_status = _raw_pytest_status(self.phases)
        reports = [
            self.phases[name]
            for name in ("setup", "call", "teardown")
            if name in self.phases
        ]
        failed_reports = [
            (phase, self.phases[phase])
            for phase in ("setup", "call", "teardown")
            if phase in self.phases and self.phases[phase]["outcome"] == "failed"
        ]

        if failed_reports:
            status = "不通过"
            failed_phase, selected = failed_reports[-1]
            reason = str(
                selected.get("assessment_reason")
                or f"pytest {failed_phase} 阶段发生未处理失败"
            )
            missing_evidence: list[str] = []
        else:
            selected = next(
                (
                    report
                    for report in reversed(reports)
                    if report.get("assessment_status") in ASSESSMENT_STATUSES
                ),
                None,
            )
            if selected is not None:
                status = str(selected["assessment_status"])
                reason = str(selected.get("assessment_reason") or "用例未提供结果说明")
                missing_evidence = _normalize_missing_evidence(
                    selected.get("assessment_missing_evidence")
                )
            elif raw_status == "skipped":
                status = "不通过" if self.is_e2e else "不适用"
                reason = (
                    "E2E 用例被 pytest 跳过，未显式产生四态测评结论"
                    if self.is_e2e
                    else "pytest 未执行该测试"
                )
                missing_evidence = []
            elif raw_status == "passed":
                status = "通过"
                reason = "pytest 测试通过，但用例未提供显式测评说明"
                missing_evidence = []
            else:
                status = "无法判定"
                reason = "pytest 会话结束前未执行该用例"
                missing_evidence = ["用例执行结果"]

        return {
            "nodeid": self.nodeid,
            "test_case_id": self.test_case_id,
            "name": self.name,
            "status": status,
            "reason": reason,
            "missing_evidence": missing_evidence,
            "duration_seconds": round(
                sum(float(report["duration_seconds"]) for report in reports), 6
            ),
            "pytest_status": raw_status,
            "phases": self.phases,
        }


class ResultCollector:
    """Aggregate pytest phase reports into one stable record per collected item."""

    def __init__(self, output_path: Path, *, run_id: str | None = None) -> None:
        self.output_path = output_path
        self.run_id = run_id or os.environ.get("AGENT_TEST_RUN_ID") or uuid.uuid4().hex
        self.started_at = _utc_now()
        self.started_monotonic = time.monotonic()
        self.collected_count = 0
        self.internal_errors: list[str] = []
        self.collection_errors: list[str] = []
        self._cases: dict[str, _CaseState] = {}

    def register_item(self, item: pytest.Item) -> None:
        module = getattr(item, "module", None)
        class_doc = inspect.getdoc(getattr(item, "cls", None)) or ""
        test_case_id = str(getattr(module, "TEST_CASE_ID", "") or "").strip()
        if not test_case_id:
            match = _TEST_ID_PATTERN.search(class_doc)
            test_case_id = match.group(1).strip() if match else item.nodeid
        name_match = _TEST_NAME_PATTERN.search(class_doc)
        name = name_match.group(1).strip() if name_match else getattr(item, "name", item.nodeid)
        self._cases.setdefault(
            item.nodeid,
            _CaseState(
                nodeid=item.nodeid,
                test_case_id=test_case_id,
                name=name,
                is_e2e="e2e" in getattr(item, "keywords", {}),
            ),
        )

    def record_report(self, item: pytest.Item, report: pytest.TestReport) -> None:
        self.register_item(item)
        self._cases[item.nodeid].record(report)

    def build_payload(self, *, exit_status: int, finished_at: str | None = None) -> dict[str, object]:
        cases = [case.serialize() for case in self._cases.values()]
        summary = {status: 0 for status in ASSESSMENT_STATUSES}
        for case in cases:
            summary[str(case["status"])] += 1
        summary["total"] = len(cases)
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "phase": os.environ.get("AGENT_TEST_PHASE", ""),
            "session": {
                "started_at": self.started_at,
                "finished_at": finished_at or _utc_now(),
                "duration_seconds": round(time.monotonic() - self.started_monotonic, 6),
                "exitstatus": int(exit_status),
                "pytest_status": _exit_status_name(exit_status),
                "collected": self.collected_count,
                "reported_cases": len(cases),
                "internal_errors": list(self.internal_errors),
                "collection_errors": list(self.collection_errors),
            },
            "summary": summary,
            "cases": cases,
        }

    def write(self, *, exit_status: int) -> None:
        _atomic_write_json(self.output_path, self.build_payload(exit_status=exit_status))


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("agent-test-tool")
    group.addoption(
        "--agent-result-json",
        action="store",
        default=None,
        metavar="PATH",
        help="Write structured four-state Agent assessment results to PATH",
    )


def pytest_configure(config: pytest.Config) -> None:
    output_path = config.getoption("--agent-result-json", default=None)
    if output_path:
        plugin = _ResultPlugin(ResultCollector(Path(output_path).resolve()))
        config.pluginmanager.register(plugin, "agent-test-tool-result-writer")


class _ResultPlugin:
    """Hold per-session state so subprocesses and nested pytest runs stay isolated."""

    def __init__(self, collector: ResultCollector) -> None:
        self.collector = collector

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        """Register only items left after pytest marker and keyword deselection."""
        self.collector.collected_count = len(items)
        for item in items:
            self.collector.register_item(item)

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            self.collector.collection_errors.append(str(report.longrepr))

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo):
        """Observe reports after test-local hook wrappers attach assessment properties."""
        outcome = yield
        self.collector.record_report(item, outcome.get_result())

    def pytest_internalerror(self, excrepr: object) -> None:
        self.collector.internal_errors.append(str(excrepr))

    def pytest_sessionfinish(self, exitstatus: int) -> None:
        self.collector.write(exit_status=int(exitstatus))
