"""Command-line entry point for the complete AgentTestTool workflow."""

from __future__ import annotations

import argparse
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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    execution = run_workflow(
        WorkflowConfig(
            agent=args.agent,
            output_parent=args.output_dir,
            repeat=args.repeat,
            smoke_timeout_seconds=args.smoke_timeout,
            business_timeout_seconds=args.business_timeout,
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
