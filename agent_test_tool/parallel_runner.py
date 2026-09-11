"""Schedule isolated pytest shards, then run exclusive cases without overlap."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

from agent_models.factory import AgentModelFactory
from agent_models.processes import ProcessCleanupError, run_managed_process
from agent_test_tool.parallel_results import merge_worker_results
from agent_test_tool.runner import (
    PhaseExecution, ProcessRunner, TEST_CASES_ROOT, WorkflowConfig,
    _run_pytest_phase, _write_json,
)


def run_parallel_business(
    config: WorkflowConfig, run_id: str, run_directory: Path, process_runner: ProcessRunner
) -> PhaseExecution:
    """Use a single deadline and a fixed concurrency ceiling for the business phase."""
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    deadline = started + config.business_timeout_seconds
    runner = run_managed_process if process_runner is subprocess.run else process_runner
    common = dict(
        selection="e2e and not smoke",
        test_paths=config.business_paths or (TEST_CASES_ROOT,),
        run_id=run_id, run_directory=run_directory, agent=config.agent,
        repeat=config.repeat, case_suite=config.suite, process_runner=runner,
    )
    try:
        inventory = _run_pytest_phase(
            phase="business-collection", collect_only=True,
            timeout_seconds=max(0.001, deadline - time.monotonic()), **common,
        )
    except Exception as error:
        reason = f"Business collection failed: {type(error).__name__}"
        stdout_path = run_directory / "business-collection.stdout.log"
        stderr_path = run_directory / "business-collection.stderr.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(reason, encoding="utf-8")
        inventory = PhaseExecution(
            "business-collection", (), 1,
            {"cases": [], "session": {"internal_errors": [reason]}},
            stdout_path, stderr_path,
        )
    records = inventory.result.get("cases", [])
    session = inventory.result.get("session", {})
    valid = (
        inventory.returncode == 0 and not inventory.timed_out
        and isinstance(records, list) and bool(records) and isinstance(session, dict)
        and not session.get("collection_errors") and not session.get("internal_errors")
        and session.get("collected") == len(records)
        and session.get("reported_cases") == len(records)
        and all(isinstance(case, dict) and isinstance(case.get("nodeid"), str) for case in records)
    )
    if valid:
        valid = len({case["nodeid"] for case in records}) == len(records)
    if not valid:
        known: dict[str, dict[str, Any]] = {}
        if isinstance(records, list):
            for case in records:
                if isinstance(case, dict) and isinstance(case.get("nodeid"), str):
                    known.setdefault(case["nodeid"], case)
        failed = merge_worker_results(
            [], expected_nodeids=list(known), collected_cases=list(known.values()),
            run_id=run_id, case_suite=config.suite, duration_seconds=time.monotonic() - started,
        )
        failed["session"]["exitstatus"] = 1
        failed["session"]["internal_errors"].insert(0, "Business collection failed or was incomplete")
        if isinstance(session, dict):
            for field in ("collection_errors", "internal_errors"):
                details = session.get(field)
                if isinstance(details, list):
                    failed["session"][field].extend(str(detail) for detail in details)
        failed["session"]["started_at"] = started_at
        failed["session"]["finished_at"] = datetime.now(timezone.utc).isoformat()
        _write_json(run_directory / "business-results.json", failed)
        return PhaseExecution(
            "business", inventory.command, 1, failed,
            inventory.stdout_path, inventory.stderr_path, inventory.timed_out,
        )
    expected = [case["nodeid"] for case in records]
    block_reason = AgentModelFactory.parallel_block_reason(config.agent)
    parallel = [
        case["nodeid"] for case in records
        if case.get("execution_policy") == "isolated" and block_reason is None
    ]
    parallel_set = set(parallel)
    exclusive = [case["nodeid"] for case in records if case["nodeid"] not in parallel_set]
    shards = [parallel[index::config.business_workers] for index in range(config.business_workers)]
    shards = [shard for shard in shards if shard]
    executions: list[PhaseExecution] = []
    errors: list[str] = []
    plan = {
        "workers": config.business_workers, "parallel_count": len(parallel),
        "exclusive_count": len(exclusive), "shards": shards, "exclusive": exclusive,
        "parallel_block_reason": block_reason,
    }
    _write_json(run_directory / "business-plan.json", plan)

    def execute(name: str, nodeids: list[str], environment: dict[str, str]) -> PhaseExecution:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Business phase deadline expired before worker start")
        selection = run_directory / f"{name}-selection.json"
        selection.write_text(json.dumps(nodeids, ensure_ascii=False), encoding="utf-8")
        return _run_pytest_phase(
            phase=name, nodeids_file=selection, environment_overrides=environment,
            require_isolated=name.startswith("business-worker-"),
            timeout_seconds=remaining, **common,
        )

    try:
        if shards:
            with ExitStack() as profiles:
                environments = [
                    profiles.enter_context(AgentModelFactory.worker_environment(config.agent))
                    for _ in shards
                ]
                with ThreadPoolExecutor(max_workers=config.business_workers) as pool:
                    futures = [
                        pool.submit(execute, f"business-worker-{index + 1}", shard, environment)
                        for index, (shard, environment) in enumerate(zip(shards, environments))
                    ]
                    # Wait for all workers before profile cleanup or exclusive execution.
                    worker_errors: list[Exception] = []
                    for future in futures:
                        try:
                            executions.append(future.result())
                        except Exception as error:
                            worker_errors.append(error)
                for error in worker_errors:
                    if isinstance(error, ProcessCleanupError):
                        raise error
                    errors.append(f"Worker scheduling failed: {type(error).__name__}")
        if exclusive and not errors and not any(execution.timed_out for execution in executions):
            executions.append(execute("business-exclusive", exclusive, {}))
    except Exception as error:
        # No retry: a worker may have already produced external side effects.
        errors.append(f"Business scheduling failed: {type(error).__name__}")
    payloads: list[dict[str, Any]] = []
    for execution in executions:
        payload = dict(execution.result)
        raw_session = payload.get("session")
        worker_session = dict(raw_session) if isinstance(raw_session, dict) else {}
        raw_errors = worker_session.get("internal_errors")
        worker_session["internal_errors"] = list(raw_errors) if isinstance(raw_errors, list) else []
        raw_cases = payload.get("cases")
        if not isinstance(raw_session, dict) or not isinstance(raw_cases, list):
            worker_session["internal_errors"].append("Invalid worker result payload")
        payload["cases"] = raw_cases if isinstance(raw_cases, list) else []
        if execution.timed_out or execution.returncode not in (0, 1):
            worker_session["internal_errors"] = [
                *worker_session.get("internal_errors", []), "Worker process did not finish normally",
            ]
        worker_session["exitstatus"] = execution.returncode
        assigned = json.loads(
            (run_directory / f"{execution.name}-selection.json").read_text(encoding="utf-8")
        )
        returned = [case.get("nodeid") for case in payload.get("cases", []) if isinstance(case, dict)]
        if sorted(assigned) != sorted(str(nodeid) for nodeid in returned):
            worker_session["internal_errors"] = [
                *worker_session.get("internal_errors", []), "Worker assignment/result mismatch",
            ]
            payload["cases"] = [
                case for case in payload.get("cases", [])
                if isinstance(case, dict) and case.get("nodeid") in assigned
            ]
        payload["session"] = worker_session
        payloads.append(payload)
    result = merge_worker_results(
        payloads, expected_nodeids=expected, collected_cases=records,
        run_id=run_id, case_suite=config.suite,
        duration_seconds=time.monotonic() - started,
    )
    result["session"]["internal_errors"].extend(errors)
    result["session"]["started_at"] = started_at
    result["session"]["finished_at"] = datetime.now(timezone.utc).isoformat()
    if errors:
        result["session"]["exitstatus"] = 1
    result["scheduling"] = plan
    plan["commands"] = [list(execution.command) for execution in executions]
    _write_json(run_directory / "business-plan.json", plan)
    _write_json(run_directory / "business-results.json", result)
    stdout = run_directory / "business.stdout.log"
    stderr = run_directory / "business.stderr.log"
    stdout.write_text("\n".join(str(item.stdout_path) for item in executions), encoding="utf-8")
    stderr.write_text("\n".join(errors), encoding="utf-8")
    return PhaseExecution(
        "business", inventory.command, result["session"]["exitstatus"], result, stdout, stderr,
        any(item.timed_out for item in executions) or time.monotonic() >= deadline,
    )
