"""Run mother-case scripts one by one against a real Agent CLI and record results."""

from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
MOTHER_ROOT = ROOT / "test_cases" / "mother_cases"
MANIFEST_PATH = ROOT / "configs" / "mother_cases_v3.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "mother-verification"
VALID_STATUSES = frozenset({"通过", "不通过", "不适用", "无法判定"})


@dataclass(frozen=True, slots=True)
class MotherScript:
    case_id: str
    path: Path
    priority: str
    category: str
    sha256: str


def _literal_constants(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            constants[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return constants


def _manifest_index() -> dict[str, Mapping[str, Any]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        str(case["source_case_id"]): case
        for case in payload["cases"]
        if isinstance(case, Mapping)
    }


def discover_scripts() -> tuple[MotherScript, ...]:
    """Discover one concrete script per mother case without importing test modules."""

    manifest = _manifest_index()
    found: list[MotherScript] = []
    seen: set[str] = set()
    for path in sorted(MOTHER_ROOT.glob("test_*.py")):
        constants = _literal_constants(path)
        case_id = str(constants.get("TEST_CASE_ID") or "").strip()
        if not case_id.startswith("TC-"):
            continue
        if case_id in seen:
            raise ValueError(f"重复母用例脚本 ID：{case_id}")
        if constants.get("TEST_CASE_LEVEL") != "mother":
            raise ValueError(f"{path} 缺少 TEST_CASE_LEVEL='mother'")
        try:
            record = manifest[case_id]
        except KeyError as error:
            raise ValueError(f"{path} 的 {case_id} 不在母用例 manifest 中") from error
        seen.add(case_id)
        found.append(
            MotherScript(
                case_id=case_id,
                path=path,
                priority=str(record["priority"]),
                category=str(record["category"]),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    priority_order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    return tuple(sorted(found, key=lambda item: (priority_order[item.priority], item.case_id)))


def _read_index(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "cases": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), dict):
        raise ValueError(f"验证索引格式无效：{path}")
    return payload


def _write_index(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _verified_for_current_script(
    index: Mapping[str, Any],
    script: MotherScript,
) -> bool:
    cases = index.get("cases")
    if not isinstance(cases, Mapping):
        return False
    entry = cases.get(script.case_id)
    if not isinstance(entry, Mapping) or entry.get("script_sha256") != script.sha256:
        return False
    attempts = entry.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return False
    latest = attempts[-1]
    return isinstance(latest, Mapping) and latest.get("verified") is True


def _validate_result(path: Path, expected_case_id: str) -> tuple[bool, str, str]:
    if not path.is_file():
        return False, "", "pytest 未生成结构化结果 JSON"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return False, "", f"结构化结果无法读取：{type(error).__name__}"
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 1:
        return False, "", "独立验证必须恰好报告一条用例"
    case = cases[0]
    if not isinstance(case, Mapping):
        return False, "", "结构化用例结果不是对象"
    actual_case_id = str(case.get("test_case_id") or "")
    status = str(case.get("status") or "")
    reason = str(case.get("reason") or "")
    if actual_case_id != expected_case_id:
        return False, status, f"报告 ID 不匹配：{actual_case_id or '<missing>'}"
    if status not in VALID_STATUSES:
        return False, status, f"报告未产生有效四态结果：{status or '<missing>'}"
    if not reason.strip():
        return False, status, "四态结果缺少原因"
    return True, status, reason.strip()


def _select_scripts(
    scripts: Iterable[MotherScript],
    *,
    priorities: set[str],
    case_ids: set[str],
) -> list[MotherScript]:
    selected = [
        script
        for script in scripts
        if (not priorities or script.priority in priorities)
        and (not case_ids or script.case_id in case_ids)
    ]
    missing = case_ids.difference(script.case_id for script in selected)
    if missing:
        raise ValueError(f"未找到指定母用例脚本：{', '.join(sorted(missing))}")
    return selected


def verify_script(
    script: MotherScript,
    *,
    agent: str,
    output_root: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run exactly one script and return a resumable attempt record."""

    case_root = output_root / script.priority / script.case_id
    attempt_number = 1 + len(list(case_root.glob("attempt-*")))
    attempt_root = case_root / f"attempt-{attempt_number:03d}"
    evidence_root = attempt_root / "evidence"
    result_path = attempt_root / "result.json"
    stdout_path = attempt_root / "stdout.txt"
    stderr_path = attempt_root / "stderr.txt"
    attempt_root.mkdir(parents=True, exist_ok=False)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "agent_test_tool.result_plugin",
        str(script.path.relative_to(ROOT)),
        f"--agent={agent}",
        "--case-suite=mother",
        "--evidence-dir",
        str(evidence_root),
        "--agent-result-json",
        str(result_path),
        "-q",
    ]
    environment = os.environ.copy()
    environment["AGENT_TEST_CASE_SUITE"] = "mother"
    environment["AGENT_TEST_PHASE"] = "mother_individual_verification"
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    timed_out = False
    returncode: int | None = None
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
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
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    verified, status, reason = _validate_result(result_path, script.case_id)
    if timed_out:
        verified = False
        reason = f"独立验证超过 {timeout_seconds:g} 秒"
    return {
        "attempt": attempt_number,
        "started_at": started_at.isoformat(),
        "duration_seconds": round(time.monotonic() - started, 3),
        "command": command,
        "returncode": returncode,
        "timed_out": timed_out,
        "verified": verified,
        "status": status,
        "reason": reason,
        "result_json": str(result_path.relative_to(ROOT)),
        "evidence_root": str(evidence_root.relative_to(ROOT)),
        "stdout": str(stdout_path.relative_to(ROOT)),
        "stderr": str(stderr_path.relative_to(ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default="codebuddy")
    parser.add_argument("--priority", action="append", choices=("P1", "P2", "P3", "P4"))
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--rerun", action="store_true")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases 必须是正整数")

    output_root = args.output.resolve()
    index_path = output_root / "index.json"
    index = _read_index(index_path)
    selected = _select_scripts(
        discover_scripts(),
        priorities=set(args.priority or ()),
        case_ids=set(args.case_id),
    )
    pending = [
        script
        for script in selected
        if args.rerun or not _verified_for_current_script(index, script)
    ]
    if args.max_cases is not None:
        pending = pending[: args.max_cases]
    print(f"selected={len(selected)} pending={len(pending)} output={output_root}")

    cases = index.setdefault("cases", {})
    failures = 0
    for position, script in enumerate(pending, start=1):
        print(f"[{position}/{len(pending)}] {script.case_id} ({script.priority}/{script.category})")
        attempt = verify_script(
            script,
            agent=args.agent,
            output_root=output_root,
            timeout_seconds=args.timeout,
        )
        entry = cases.setdefault(
            script.case_id,
            {
                "script": str(script.path.relative_to(ROOT)),
                "priority": script.priority,
                "category": script.category,
                "attempts": [],
            },
        )
        entry["script_sha256"] = script.sha256
        entry["attempts"].append(attempt)
        index["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_index(index_path, index)
        print(
            f"  verified={attempt['verified']} status={attempt['status'] or '-'} "
            f"duration={attempt['duration_seconds']}s"
        )
        if not attempt["verified"]:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
