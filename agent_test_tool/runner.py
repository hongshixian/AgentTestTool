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
SMOKE_CASES_ROOT = TEST_CASES_ROOT / "smoke"
BLACK_BOX_CASES_ROOT = TEST_CASES_ROOT / "black_box"
GREY_BOX_CASES_ROOT = TEST_CASES_ROOT / "grey_box"
WHITE_BOX_CASES_ROOT = TEST_CASES_ROOT / "white_box"
CASE_SUITES = frozenset({"all", "black_box", "grey_box", "white_box"})
CASE_SUITE_ROOTS = {
    "black_box": BLACK_BOX_CASES_ROOT,
    "grey_box": GREY_BOX_CASES_ROOT,
    "white_box": WHITE_BOX_CASES_ROOT,
}
TEST_OBJECT_NAMES = {
    "codebuddy": "CodeBuddy Code CLI",
    "opencode": "OpenCode CLI",
}


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    """Settings for one complete assessment workflow."""

    agent: str
    output_parent: Path
    repeat: int = 1
    smoke_timeout_seconds: float = 900.0
    business_timeout_seconds: float = 86_400.0
    suite: str = "black_box"
    business_paths: tuple[Path, ...] = ()
    business_selection_source: str | None = None
    run_id: str | None = None
    business_workers: int = 1


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
    business_suites: Mapping[str, PhaseExecution]
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
    test_paths: Sequence[Path],
    run_id: str,
    run_directory: Path,
    agent: str,
    repeat: int,
    case_suite: str,
    timeout_seconds: float,
    process_runner: ProcessRunner,
    nodeids_file: Path | None = None,
    collect_only: bool = False,
    environment_overrides: Mapping[str, str] | None = None,
    require_isolated: bool = False,
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
        *(str(path) for path in test_paths),
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
        "--case-suite",
        case_suite,
    ]
    if repeat > 1:
        command_parts.extend(("--repeat", str(repeat)))
    if collect_only:
        command_parts.append("--collect-only")
    if nodeids_file is not None:
        command_parts.extend(("--agent-nodeids-file", str(nodeids_file)))
    if require_isolated:
        command_parts.append("--agent-require-isolated")
    command_parts.append("-q")
    command = tuple(command_parts)
    environment = os.environ.copy()
    environment["AGENT_TEST_RUN_ID"] = run_id
    environment["AGENT_TEST_PHASE"] = phase
    environment["AGENT_TEST_CASE_SUITE"] = case_suite
    environment["AGENT_TEST_EVIDENCE_PROFILE"] = (
        "black_box" if case_suite == "black_box" else "default"
    )
    environment.update(environment_overrides or {})

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


def _aggregate_business_phases(
    phases: Mapping[str, PhaseExecution],
    run_directory: Path,
    run_id: str,
) -> PhaseExecution | None:
    if not phases:
        return None
    cases: list[Any] = []
    internal_errors: list[str] = []
    collection_errors: list[str] = []
    command: list[str] = []
    for suite, execution in phases.items():
        phase_cases = execution.result.get("cases")
        if isinstance(phase_cases, list):
            cases.extend(phase_cases)
        session = execution.result.get("session")
        if isinstance(session, Mapping):
            for target, field in (
                (internal_errors, "internal_errors"),
                (collection_errors, "collection_errors"),
            ):
                values = session.get(field)
                if isinstance(values, list):
                    target.extend(f"{suite}: {value}" for value in values)
        command.extend(execution.command)
    returncode = 1 if any(item.returncode != 0 for item in phases.values()) else 0
    result = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "phase": "business",
        "case_suite": "all" if len(phases) > 1 else next(iter(phases)),
        "session": {
            "exitstatus": returncode,
            "collected": len(cases),
            "reported_cases": len(cases),
            "internal_errors": internal_errors,
            "collection_errors": collection_errors,
        },
        "cases": cases,
    }
    return PhaseExecution(
        name="business",
        command=tuple(command),
        returncode=returncode,
        result=result,
        stdout_path=run_directory / "business.stdout.log",
        stderr_path=run_directory / "business.stderr.log",
        timed_out=any(item.timed_out for item in phases.values()),
    )


def run_workflow(
    config: WorkflowConfig,
    *,
    process_runner: ProcessRunner = subprocess.run,
    pdf_builder: PdfBuilder = _default_pdf_builder,
) -> WorkflowExecution:
    """Run smoke, conditionally run business cases, and always build a report."""
    if config.repeat < 1:
        raise ValueError("repeat 必须是正整数")
    if config.business_workers < 1 or config.business_workers > 4:
        raise ValueError("business_workers 必须在 1 到 4 之间")
    if config.suite not in CASE_SUITES:
        raise ValueError(f"未知业务测试套件：{config.suite}")
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
        test_paths=(SMOKE_CASES_ROOT,),
        run_id=run_id,
        run_directory=run_directory,
        agent=config.agent,
        repeat=1,
        case_suite="smoke",
        timeout_seconds=config.smoke_timeout_seconds,
        process_runner=process_runner,
    )
    smoke_passed = smoke_gate_passed(smoke)
    business_suites: dict[str, PhaseExecution] = {}
    selected_suites = tuple(CASE_SUITE_ROOTS) if config.suite == "all" else (config.suite,)
    if smoke_passed and config.business_workers > 1 and config.suite != "all":
        from agent_test_tool.parallel_runner import run_parallel_business

        business_suites[config.suite] = run_parallel_business(
            config, run_id, run_directory, process_runner
        )
    elif smoke_passed:
        for suite in selected_suites:
            business_suites[suite] = _run_pytest_phase(
                phase=(f"business-{suite}" if config.suite == "all" else "business"),
                selection=f"e2e and {suite}",
                test_paths=config.business_paths or (CASE_SUITE_ROOTS[suite],),
                run_id=run_id,
                run_directory=run_directory,
                agent=config.agent,
                repeat=config.repeat,
                case_suite=suite,
                timeout_seconds=config.business_timeout_seconds,
                process_runner=process_runner,
            )
    business = _aggregate_business_phases(business_suites, run_directory, run_id)

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
        "business_suites": {
            suite: dict(execution.result)
            for suite, execution in business_suites.items()
        },
        "business_not_executed_reason": (
            None if business is not None else "冒烟测试未全部通过，未执行业务测试"
        ),
        "business_selection": {
            "workers": config.business_workers,
            "suite": config.suite,
            "source": config.business_selection_source,
            "path_count": len(config.business_paths),
            "paths": [str(path) for path in config.business_paths],
        },
        "commands": {
            "smoke": list(smoke.command),
            "business": list(business.command) if business is not None else None,
            "business_suites": {
                suite: list(execution.command)
                for suite, execution in business_suites.items()
            },
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
        business_suites=business_suites,
        smoke_passed=smoke_passed,
        exit_code=exit_code,
    )


def command_text(command: Sequence[str]) -> str:
    """Render an informational command without invoking a shell."""
    return " ".join(command)
