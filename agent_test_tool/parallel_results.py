"""Validate and merge independently collected business worker results."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence


STATUSES = ("通过", "不通过", "不适用", "无法判定")


def merge_worker_results(
    workers: Sequence[Mapping[str, Any]],
    *,
    expected_nodeids: Sequence[str],
    run_id: str,
    case_suite: str,
    duration_seconds: float,
    collected_cases: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Preserve collection order and expose missing or duplicate worker records.

    Expected IDs come from the actual pytest collection, including repeat
    parameters. A worker crash must never silently shrink the report denominator.
    """
    if len(set(expected_nodeids)) != len(expected_nodeids):
        raise ValueError("Duplicate node IDs in business collection")
    expected = set(expected_nodeids)
    metadata = {case["nodeid"]: case for case in collected_cases}
    received: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for index, worker in enumerate(workers):
        session = worker.get("session")
        cases = worker.get("cases")
        if not isinstance(session, Mapping) or not isinstance(cases, list):
            errors.append(f"Worker {index}: invalid result payload")
            continue
        for key in ("internal_errors", "collection_errors"):
            if session.get(key):
                errors.append(f"Worker {index}: {key}")
        if session.get("exitstatus") not in (0, 1):
            errors.append(f"Worker {index}: abnormal pytest exit")
        if session.get("reported_cases") != len(cases):
            errors.append(f"Worker {index}: reported case count mismatch")
        if session.get("collected", len(cases)) != len(cases):
            errors.append(f"Worker {index}: collected case count mismatch")
        if session.get("exitstatus") == 1 and not any(
            isinstance(item, Mapping) and item.get("status") == "不通过" for item in cases
        ):
            errors.append(f"Worker {index}: failed exit without a failing case")
        for item in cases:
            if not isinstance(item, Mapping):
                errors.append(f"Worker {index}: invalid case record")
                continue
            nodeid = item.get("nodeid")
            if not isinstance(nodeid, str) or nodeid not in expected:
                errors.append(f"Worker {index}: unexpected node ID")
                continue
            if nodeid in received:
                errors.append(f"Duplicate result: {nodeid}")
                received[nodeid] = _failed_case(nodeid, "重复收到用例结果，无法确认执行唯一性", metadata.get(nodeid))
                continue
            if item.get("status") not in STATUSES or item.get("pytest_status") == "not_run":
                errors.append(f"Incomplete result: {nodeid}")
                received[nodeid] = _failed_case(nodeid, "worker 未完成用例执行或未返回有效四态结果", metadata.get(nodeid))
            else:
                received[nodeid] = dict(item)
    cases = []
    for nodeid in expected_nodeids:
        if nodeid not in received:
            errors.append(f"Missing result: {nodeid}")
            received[nodeid] = _failed_case(nodeid, "worker 未返回该用例结果，执行不完整", metadata.get(nodeid))
        cases.append(received[nodeid])
    counts = Counter(case["status"] for case in cases)
    by_level: dict[str, dict[str, int]] = {}
    for case in cases:
        level = str(case.get("case_level") or "unknown")
        summary = by_level.setdefault(level, {**dict.fromkeys(STATUSES, 0), "total": 0})
        summary[case["status"]] += 1
        summary["total"] += 1
    exitstatus = 1 if errors or counts["不通过"] else 0
    return {
        "schema_version": 1,
        "run_id": run_id,
        "phase": "business",
        "case_suite": case_suite,
        "session": {
            "exitstatus": exitstatus,
            "duration_seconds": duration_seconds,
            "collected": len(expected_nodeids),
            "reported_cases": len(cases),
            "internal_errors": errors,
            "collection_errors": [],
        },
        "cases": cases,
        "summary_by_case_level": by_level,
        "summary": {**{status: counts[status] for status in STATUSES}, "total": len(cases)},
    }


def _failed_case(
    nodeid: str, reason: str, metadata: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    return {
        **{key: value for key, value in (metadata or {}).items() if key in {
            "test_case_id", "name", "case_level", "source_case_id", "representative_child_id"
        }},
        "nodeid": nodeid,
        "test_case_id": (metadata or {}).get("test_case_id", nodeid),
        "name": (metadata or {}).get("name", nodeid),
        "status": "不通过",
        "reason": reason,
        "pytest_status": "error",
        "phases": {},
        "duration_seconds": 0.0,
        "missing_evidence": [],
    }
