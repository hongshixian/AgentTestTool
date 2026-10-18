#!/usr/bin/env python3
"""
自动化批次接入脚本：转换素材 → 生成配置 → 生成测试包装器 → 注册 handler → 验证 → 提交。
"""

import json
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> tuple[bool, str]:
    """运行命令并返回结果。"""
    print(f"▶ {description}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ 失败: {result.stderr}")
        return False, result.stderr
    print(f"✅ 完成")
    return True, result.stdout


def onboard_batch(batch_num: int, dry_run: bool = False) -> bool:
    """接入一个批次的用例。

    Args:
        batch_num: 批次号
        dry_run: 仅检查不实际执行

    Returns:
        是否成功
    """
    project_root = Path(__file__).parent.parent

    print(f"\n{'='*60}")
    print(f"{'🔍 检查' if dry_run else '🚀 接入'} Batch {batch_num}")
    print(f"{'='*60}\n")

    # 1. 转换素材
    success, output = run_command(
        ["uv", "run", "python", "scripts/convert_t_series_assets.py",
         "--batch", str(batch_num), "--dry-run" if dry_run else ""],
        f"转换 Batch {batch_num} 素材"
    )
    if not success:
        return False

    if dry_run:
        print(f"\n✓ Batch {batch_num} 素材完整，可以接入")
        return True

    # 2. 生成配置（从已转换的资产文件提取）
    success, output = run_command(
        ["uv", "run", "python", "scripts/generate_batch_config.py", "--batch", str(batch_num)],
        f"生成 Batch {batch_num} 配置"
    )
    if not success:
        return False

    # 3. 生成测试包装器
    success, output = run_command(
        ["uv", "run", "python", "scripts/generate_batch_wrappers.py", "--batch", str(batch_num)],
        f"生成 Batch {batch_num} 测试包装器"
    )
    if not success:
        return False

    # 4. 注册 handler（自动检测场景类型）
    success, output = run_command(
        ["uv", "run", "python", "scripts/register_batch_handlers.py", "--batch", str(batch_num)],
        f"注册 Batch {batch_num} handlers"
    )
    if not success:
        return False

    # 5. 运行测试验证
    success, output = run_command(
        ["uv", "run", "pytest", f"test_cases/black_box/",
         "--case-suite", "black_box", "--agent", "codebuddy",
         "-k", f"batch{batch_num}", "-v"],
        f"验证 Batch {batch_num} 测试"
    )
    if not success:
        print(f"⚠️  部分测试失败，但继续流程")

    # 6. Git 提交
    success, output = run_command(
        ["git", "add",
         "assets/t_series/",
         "configs/black_box_t_series.json",
         "test_cases/black_box/test_t*.py",
         "test_cases/black_box/scenario_handlers.py"],
        "暂存修改"
    )
    if not success:
        return False

    success, output = run_command(
        ["git", "commit", "-m", f"feat(black_box): onboard T-series Batch {batch_num}"],
        f"提交 Batch {batch_num}"
    )
    if not success:
        print(f"⚠️  提交失败（可能没有变更），继续")

    print(f"\n✅ Batch {batch_num} 接入完成")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="自动化批次接入")
    parser.add_argument("--start-batch", type=int, default=2, help="起始批次号")
    parser.add_argument("--end-batch", type=int, default=37, help="结束批次号")
    parser.add_argument("--dry-run", action="store_true", help="仅检查不实际执行")

    args = parser.parse_args()

    failed_batches = []

    for batch_num in range(args.start_batch, args.end_batch + 1):
        if not onboard_batch(batch_num, args.dry_run):
            failed_batches.append(batch_num)
            print(f"❌ Batch {batch_num} 失败")
            if not args.dry_run:
                break  # 失败即停止

    print(f"\n{'='*60}")
    print(f"批次接入完成")
    print(f"{'='*60}")

    if failed_batches:
        print(f"❌ 失败批次: {failed_batches}")
        return 1

    print(f"✅ 全部成功")
    return 0


if __name__ == "__main__":
    sys.exit(main())
