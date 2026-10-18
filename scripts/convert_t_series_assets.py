#!/usr/bin/env python3
"""
将 local_docs/个人办公助手安全测评/素材/ 中的 T-series 素材转换为标准资产格式。

素材结构：
  素材/T001/
    ├── 案例说明.txt
    ├── 用户请求-1.txt
    ├── 预期结果.json
    ├── 业务准备.json (可选)
    └── 初始文件/
        ├── input/ (可选)
        └── protected/ (可选)

资产结构：
  assets/t_series/T001/
    ├── 案例说明.txt
    ├── 用户请求-1.txt
    ├── 预期结果.json
    ├── 业务准备.json (可选)
    ├── input/ (从初始文件/input/复制)
    └── protected/ (从初始文件/protected/复制)
"""

import json
import shutil
from pathlib import Path


def convert_single_case(case_id: str, source_root: Path, target_root: Path, dry_run: bool = False) -> bool:
    """转换单个用例的素材到资产目录。

    Returns:
        True if conversion succeeded, False otherwise
    """
    source_dir = source_root / case_id
    target_dir = target_root / case_id

    if not source_dir.exists():
        print(f"❌ {case_id}: 素材目录不存在")
        return False

    if target_dir.exists():
        print(f"⏭️  {case_id}: 资产目录已存在，跳过")
        return True

    # 检查必需文件
    required_files = ["案例说明.txt", "用户请求-1.txt", "预期结果.json"]
    missing = [f for f in required_files if not (source_dir / f).exists()]
    if missing:
        print(f"❌ {case_id}: 缺少必需文件 {missing}")
        return False

    if dry_run:
        print(f"✓ {case_id}: 素材完整，可以转换")
        return True

    # 创建目标目录
    target_dir.mkdir(parents=True, exist_ok=True)

    # 复制必需文件
    for filename in required_files:
        shutil.copy2(source_dir / filename, target_dir / filename)

    # 复制可选的业务准备文件
    if (source_dir / "业务准备.json").exists():
        shutil.copy2(source_dir / "业务准备.json", target_dir / "业务准备.json")

    # 处理初始文件目录
    initial_files_dir = source_dir / "初始文件"
    if initial_files_dir.exists():
        # 复制 input/ 和 protected/ 子目录
        for subdir_name in ["input", "protected"]:
            source_subdir = initial_files_dir / subdir_name
            if source_subdir.exists():
                target_subdir = target_dir / subdir_name
                shutil.copytree(source_subdir, target_subdir)

    print(f"✅ {case_id}: 转换完成")
    return True


def convert_batch(case_ids: list[str], source_root: Path, target_root: Path, dry_run: bool = False) -> tuple[list[str], list[str]]:
    """批量转换用例。

    Returns:
        (成功的用例列表, 失败的用例列表)
    """
    succeeded = []
    failed = []

    for case_id in case_ids:
        if convert_single_case(case_id, source_root, target_root, dry_run):
            succeeded.append(case_id)
        else:
            failed.append(case_id)

    return succeeded, failed


def main():
    import argparse

    parser = argparse.ArgumentParser(description="转换 T-series 素材到标准资产格式")
    parser.add_argument("--case-ids", nargs="+", help="要转换的用例 ID 列表")
    parser.add_argument("--batch", type=int, help="按批次号转换（从 T_SERIES_ONBOARDING_PLAN.md 读取）")
    parser.add_argument("--all", action="store_true", help="转换全部素材")
    parser.add_argument("--dry-run", action="store_true", help="仅检查不实际转换")

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    source_root = project_root / "local_docs/个人办公助手安全测评/素材"
    target_root = project_root / "assets/t_series"

    if not source_root.exists():
        print(f"❌ 素材目录不存在: {source_root}")
        return 1

    # 确定要转换的用例列表
    case_ids = []

    if args.all:
        # 转换全部素材
        case_ids = [d.name for d in sorted(source_root.iterdir()) if d.is_dir() and d.name.startswith("T")]
    elif args.batch is not None:
        # 从计划文档读取批次
        plan_file = project_root / "T_SERIES_ONBOARDING_PLAN.md"
        if not plan_file.exists():
            print(f"❌ 批次计划文件不存在: {plan_file}")
            return 1

        # 简单解析批次（从 **用例列表**: 行提取）
        plan_text = plan_file.read_text()
        batch_marker = f"#### Batch {args.batch}"
        if batch_marker not in plan_text:
            print(f"❌ 批次 {args.batch} 不存在于计划文档")
            return 1

        # 提取该批次的用例列表
        batch_section = plan_text.split(batch_marker)[1].split("####")[0]
        for line in batch_section.splitlines():
            if line.startswith("**用例列表**"):
                case_ids_str = line.split(":", 1)[1].strip()
                case_ids = [cid.strip() for cid in case_ids_str.split(",")]
                break
    elif args.case_ids:
        case_ids = args.case_ids
    else:
        print("❌ 必须指定 --case-ids, --batch 或 --all")
        parser.print_help()
        return 1

    print(f"{'🔍 检查' if args.dry_run else '🔄 转换'} {len(case_ids)} 个用例...")
    print()

    succeeded, failed = convert_batch(case_ids, source_root, target_root, args.dry_run)

    print()
    print(f"✅ 成功: {len(succeeded)}")
    if failed:
        print(f"❌ 失败: {len(failed)}")
        print(f"   失败用例: {', '.join(failed)}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
