"""Run smoke-gated Agent CLI assessments and persist their structured results."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from configs import load_project_environment


PASS_STATUS = "通过"
FAIL_STATUS = "不通过"
REPORT_SCHEMA_VERSION = 1
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEST_CASES_ROOT = PACKAGE_ROOT / "test_cases"
TEST_OBJECT_NAMES = {
    "codebuddy": "CodeBuddy Code CLI",
}


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    """Settings for one complete assessment workflow."""

    agent: str
    output_parent: Path
    repeat: int = 1
    smoke_timeout_seconds: float = 900.0
    business_timeout_seconds: float = 86_400.0
    run_id: str | None = None


@dataclass(frozen=True, slots=True)
class PhaseExecution:
    """One pytest phase and its parsed structured result."""

    name: str
    command: tuple[str, ...]
    returncode: int
    result: Mapping[str, Any]
    stdout_path: Path
    stderr_path: Path
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowExecution:
    """Artifacts and terminal state produced by the complete workflow."""

    run_id: str
    run_directory: Path
    report_json: Path
    report_pdf: Path | None
    smoke: PhaseExecution
    business: PhaseExecution | None
    smoke_passed: bool
    exit_code: int


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]
PdfBuilder = Callable[[Mapping[str, Any], Path], None]


def create_run_id(now: datetime | None = None) -> str:
    """Return a sortable run identifier without exposing product information."""
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:12]}"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically persist one UTF-8 JSON document."""
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_phase_result(
    result_path: Path,
    *,
    run_id: str,
    phase: str,
    returncode: int,
    error: str | None = None,
) -> Mapping[str, Any]:
    if result_path.is_file():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            error = f"结构化结果无法读取：{type(exc).__name__}: {exc}"
        else:
            if isinstance(payload, dict):
                return payload
            error = "结构化结果根节点不是 JSON object"

    reason = error or "pytest 未生成结构化结果"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "phase": phase,
        "session": {
            "exitstatus": returncode,
            "collected": 0,
            "internal_errors": [reason],
        },
        "cases": [],
        "summary": {
            PASS_STATUS: 0,
            FAIL_STATUS: 1,
            "不适用": 0,
            "无法判定": 0,
        },
        "phase_error": reason,
    }


def _run_pytest_phase(
    *,
    phase: str,
    selection: str,
    run_id: str,
    run_directory: Path,
    agent: str,
    repeat: int,
    timeout_seconds: float,
    process_runner: ProcessRunner,
) -> PhaseExecution:
    result_path = run_directory / f"{phase}-results.json"
    stdout_path = run_directory / f"{phase}.stdout.log"
    stderr_path = run_directory / f"{phase}.stderr.log"
    evidence_parent = run_directory / "evidence" / phase
    evidence_parent.mkdir(parents=True, exist_ok=True)

    command_parts = [
        sys.executable,
        "-m",
        "pytest",
        str(TEST_CASES_ROOT),
        "-m",
        selection,
        "-p",
        "agent_test_tool.result_plugin",
        "--agent-result-json",
        str(result_path),
        "--agent",
        agent,
        "--evidence-dir",
        str(evidence_parent),
    ]
    if repeat > 1:
        command_parts.extend(("--repeat", str(repeat)))
    command_parts.append("-q")
    command = tuple(command_parts)
    environment = os.environ.copy()
    environment["AGENT_TEST_RUN_ID"] = run_id
    environment["AGENT_TEST_PHASE"] = phase

    timed_out = False
    error: str | None = None
    try:
        completed = process_runner(
            command,
            cwd=run_directory,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 1
        stdout = _coerce_subprocess_output(exc.stdout)
        stderr = _coerce_subprocess_output(exc.stderr)
        error = f"{phase} 阶段超过 {timeout_seconds:g} 秒超时"
    except OSError as exc:
        returncode = 1
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}"
        error = f"无法启动 pytest：{stderr}"

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    result = _load_phase_result(
        result_path,
        run_id=run_id,
        phase=phase,
        returncode=returncode,
        error=error,
    )
    return PhaseExecution(
        name=phase,
        command=command,
        returncode=returncode,
        result=result,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timed_out=timed_out,
    )


def _coerce_subprocess_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def smoke_gate_passed(execution: PhaseExecution) -> bool:
    """Require a non-empty smoke suite whose every case explicitly passed."""
    cases = execution.result.get("cases")
    session = execution.result.get("session")
    if execution.returncode != 0 or execution.timed_out:
        return False
    if not isinstance(cases, list) or not cases:
        return False
    if isinstance(session, Mapping):
        if session.get("internal_errors") or session.get("collection_errors"):
            return False
        if session.get("exitstatus") not in (None, 0):
            return False
        collected = session.get("collected")
        reported = session.get("reported_cases")
        if isinstance(collected, int) and collected != len(cases):
            return False
        if isinstance(reported, int) and reported != len(cases):
            return False
    return all(
        isinstance(case, Mapping) and case.get("status") == PASS_STATUS
        for case in cases
    )


def _default_pdf_builder(payload: Mapping[str, Any], output_path: Path) -> None:
    from agent_test_tool.reporting import CaseCategory, CaseResult, ReportData, generate_pdf
    from assertions.outcome import AssessmentStatus

    smoke_payload = payload.get("smoke")
    business_payload = payload.get("business")
    if not isinstance(smoke_payload, Mapping):
        raise ValueError("报告缺少有效的冒烟测试结果")
    normalized_business = (
        business_payload if isinstance(business_payload, Mapping) else None
    )
    report = ReportData.from_pytest_payloads(
        smoke_payload,
        normalized_business,
        test_target=str(payload.get("test_object") or "未指定测试对象"),
    )
    if payload.get("smoke_passed") is False and report.smoke_passed:
        session = smoke_payload.get("session")
        details: list[str] = []
        if isinstance(session, Mapping):
            for field in ("internal_errors", "collection_errors"):
                values = session.get(field)
                if isinstance(values, list):
                    details.extend(str(value) for value in values if value)
            exitstatus = session.get("exitstatus")
            if exitstatus not in (None, 0):
                details.append(f"pytest exitstatus={exitstatus}")
        report = ReportData(
            metadata=report.metadata,
            smoke_results=(
                *report.smoke_results,
                CaseResult(
                    case_id="FRAMEWORK-SMOKE-GATE",
                    name="冒烟测试阶段完整性检查",
                    status=AssessmentStatus.FAIL,
                    reason="；".join(details) or "冒烟测试阶段未满足业务测试门禁",
                    category=CaseCategory.SMOKE,
                ),
            ),
            business_results=(),
        )
    generate_pdf(report, output_path)


def run_workflow(
    config: WorkflowConfig,
    *,
    process_runner: ProcessRunner = subprocess.run,
    pdf_builder: PdfBuilder = _default_pdf_builder,
) -> WorkflowExecution:
    """Run smoke, conditionally run business cases, and always build a report."""
    if config.repeat < 1:
        raise ValueError("repeat 必须是正整数")
    if config.smoke_timeout_seconds <= 0 or config.business_timeout_seconds <= 0:
        raise ValueError("阶段超时必须大于 0")

    load_project_environment()
    run_id = config.run_id or create_run_id()
    run_directory = config.output_parent.resolve() / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc)

    smoke = _run_pytest_phase(
        phase="smoke",
        selection="e2e and smoke",
        run_id=run_id,
        run_directory=run_directory,
        agent=config.agent,
        repeat=1,
        timeout_seconds=config.smoke_timeout_seconds,
        process_runner=process_runner,
    )
    smoke_passed = smoke_gate_passed(smoke)
    business: PhaseExecution | None = None
    if smoke_passed:
        business = _run_pytest_phase(
            phase="business",
            selection="e2e and not smoke",
            run_id=run_id,
            run_directory=run_directory,
            agent=config.agent,
            repeat=config.repeat,
            timeout_seconds=config.business_timeout_seconds,
            process_runner=process_runner,
        )

    finished_at = datetime.now(timezone.utc)
    report_payload: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "agent_product": config.agent,
        "test_object": TEST_OBJECT_NAMES.get(config.agent, config.agent),
        "generated_at": finished_at.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "smoke_passed": smoke_passed,
        "smoke": dict(smoke.result),
        "business_executed": business is not None,
        "business": dict(business.result) if business is not None else None,
        "business_not_executed_reason": (
            None if business is not None else "冒烟测试未全部通过，未执行业务测试"
        ),
        "commands": {
            "smoke": list(smoke.command),
            "business": list(business.command) if business is not None else None,
        },
    }
    report_json = run_directory / "report.json"
    _write_json(report_json, report_payload)

    report_pdf = run_directory / "report.pdf"
    report_error: str | None = None
    try:
        pdf_builder(report_payload, report_pdf)
    except Exception as exc:  # report failures must preserve JSON and phase logs
        report_error = f"{type(exc).__name__}: {exc}"
        (run_directory / "report-error.txt").write_text(
            report_error + "\n",
            encoding="utf-8",
        )
        report_pdf = None

    if report_error is not None:
        exit_code = 2
    elif not smoke_passed:
        exit_code = 1
    elif business is not None and business.returncode != 0:
        exit_code = 1
    else:
        exit_code = 0

    return WorkflowExecution(
        run_id=run_id,
        run_directory=run_directory,
        report_json=report_json,
        report_pdf=report_pdf,
        smoke=smoke,
        business=business,
        smoke_passed=smoke_passed,
        exit_code=exit_code,
    )


def command_text(command: Sequence[str]) -> str:
    """Render an informational command without invoking a shell."""
    return " ".join(command)
