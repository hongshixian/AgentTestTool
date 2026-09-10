"""Command-line entry point for the complete AgentTestTool workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from agent_test_tool.runner import WorkflowConfig, run_workflow


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-test",
        description="依次执行冒烟测试、业务测试并生成 PDF 测试报告。",
    )
    parser.add_argument(
        "--business-manifest",
        type=Path,
        help=(
            "仅执行 JSON 清单 cases[].script 指定的业务测试文件；"
            "冒烟测试仍执行完整 smoke 集"
        ),
    )
    parser.add_argument(
        "--suite",
        choices=("mother", "child", "all"),
        default="child",
        help="业务测试粒度：母用例、展开子用例或两者（默认：child）",
    )
    parser.add_argument(
        "--agent",
        default="codebuddy",
        help="被测 Agent 产品（默认：codebuddy）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts"),
        help="运行产物父目录（默认：artifacts）",
    )
    parser.add_argument(
        "--repeat",
        type=_positive_int,
        default=1,
        help="业务测试的重复次数（默认：1）",
    )
    parser.add_argument(
        "--smoke-timeout",
        type=_positive_float,
        default=900.0,
        metavar="SECONDS",
        help="冒烟阶段总超时秒数（默认：900）",
    )
    parser.add_argument(
        "--business-timeout",
        type=_positive_float,
        default=86_400.0,
        metavar="SECONDS",
        help="业务阶段总超时秒数（默认：86400）",
    )
    return parser


def _manifest_paths(manifest_path: Path) -> tuple[Path, ...]:
    """Load and validate repository-local test scripts from a manifest."""
    resolved_manifest = manifest_path.resolve()
    payload = json.loads(resolved_manifest.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("业务清单必须包含非空 cases 数组")
    project_root = Path(__file__).resolve().parent.parent
    test_root = (project_root / "test_cases").resolve()
    paths: list[Path] = []
    seen: set[Path] = set()
    for index, case in enumerate(cases, start=1):
        script = case.get("script") if isinstance(case, dict) else None
        if not isinstance(script, str) or not script.strip():
            raise ValueError(f"业务清单第 {index} 项缺少 script")
        path = (project_root / script).resolve()
        if not path.is_relative_to(test_root) or path.parent != test_root:
            raise ValueError(f"业务清单脚本不在 test_cases 根目录：{script}")
        if not path.is_file() or not path.name.startswith("test_") or path.suffix != ".py":
            raise ValueError(f"业务清单脚本无效：{script}")
        if path not in seen:
            paths.append(path)
            seen.add(path)
    return tuple(paths)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.business_manifest and args.suite != "child":
        raise SystemExit("--business-manifest 目前只能与 --suite child 一起使用")
    try:
        business_paths = (
            _manifest_paths(args.business_manifest) if args.business_manifest else ()
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"业务清单读取失败：{error}") from error
    execution = run_workflow(
        WorkflowConfig(
            agent=args.agent,
            output_parent=args.output_dir,
            repeat=args.repeat,
            smoke_timeout_seconds=args.smoke_timeout,
            business_timeout_seconds=args.business_timeout,
            suite=args.suite,
            business_paths=business_paths,
            business_selection_source=(
                str(args.business_manifest.resolve()) if args.business_manifest else None
            ),
        )
    )

    print(f"RUN_ID: {execution.run_id}")
    print(f"冒烟测试：{'通过' if execution.smoke_passed else '不通过'}")
    if execution.business is None:
        print("业务测试：未执行（冒烟测试未通过）")
    else:
        print("业务测试：已执行")
    print(f"结构化报告：{execution.report_json}")
    if execution.report_pdf is not None:
        print(f"PDF 报告：{execution.report_pdf}")
    else:
        print(f"PDF 报告生成失败：{execution.run_directory / 'report-error.txt'}", file=sys.stderr)
    return execution.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
