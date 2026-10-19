#!/usr/bin/env python3
"""
自动化接入剩余所有批次的脚本。

流程：
1. 批量转换素材到资产
2. 生成配置和测试包装器
3. 自动注册 handlers
4. 验证并提交每个批次
"""

import json
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str], desc: str) -> bool:
    """运行命令并返回是否成功。"""
    print(f"▶ {desc}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    if result.returncode != 0:
        print(f"❌ 失败: {result.stderr[:500]}")
        return False
    print(f"✅ 完成")
    return True


def process_batch(batch_num: int, case_ids: list[str]) -> bool:
    """处理一个批次。"""
    print(f"\n{'='*60}")
    print(f"🚀 处理 Batch {batch_num}: {len(case_ids)} 个用例")
    print(f"{'='*60}\n")

    project_root = Path(__file__).parent.parent

    # 1. 转换素材
    if not run_cmd(
        ["uv", "run", "python", "scripts/convert_t_series_assets.py", "--case-ids"] + case_ids,
        f"转换 {len(case_ids)} 个用例的素材"
    ):
        return False

    # 2. 生成配置
    for case_id in case_ids:
        asset_dir = project_root / f"assets/t_series/{case_id}"
        if not asset_dir.exists():
            print(f"❌ {case_id} 资产目录不存在")
            return False

    # 追加到配置文件
    config_path = project_root / "configs/black_box_t_series.json"
    with open(config_path) as f:
        full_config = json.load(f)

    existing_ids = {c["case_id"] for c in full_config["cases"]}
    new_cases = []

    for case_id in case_ids:
        if case_id in existing_ids:
            continue

        asset_dir = project_root / f"assets/t_series/{case_id}"

        # 读取案例说明
        case_desc_path = asset_dir / "案例说明.txt"
        case_desc = case_desc_path.read_text(encoding="utf-8")

        # 提取题目名称
        lines = case_desc.split("\n")
        title = ""
        for i, line in enumerate(lines):
            if line.strip() == "题目名称" and i + 1 < len(lines):
                title = lines[i + 1].strip()
                break

        # 读取用户请求
        prompt_path = asset_dir / "用户请求-1.txt"
        prompt = prompt_path.read_text(encoding="utf-8").strip()

        # 检查业务准备
        has_business = (asset_dir / "业务准备.json").exists()

        # 构建配置
        config = {
            "case_id": case_id,
            "title": title,
            "timeout_seconds": 120,
            "workspace_files": [],
            "steps": [{"prompt": prompt}],
            "assertion_rules": [],
            "metadata": {
                "scenario": "single_turn",
                "has_business_state": has_business
            }
        }

        # 添加工作区文件
        for subdir in ["input", "protected"]:
            subdir_path = asset_dir / subdir
            if subdir_path.exists():
                for file in subdir_path.iterdir():
                    if file.is_file() and file.name != ".gitkeep":
                        config["workspace_files"].append({
                            "path": f"{subdir}/{file.name}",
                            "asset": f"t_series/{case_id}/{subdir}/{file.name}"
                        })

        new_cases.append(config)

    if new_cases:
        full_config["cases"].extend(new_cases)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(full_config, f, indent=2, ensure_ascii=False)
        print(f"✅ 添加 {len(new_cases)} 个新配置")

    # 3. 生成测试包装器
    for case_id in case_ids:
        if case_id in existing_ids:
            continue
        case_num = case_id.replace("T", "").lstrip("0") or "0"
        wrapper_path = project_root / f"test_cases/black_box/test_t{case_num}.py"
        if wrapper_path.exists():
            continue

        wrapper_path.write_text(f'''"""Test case {case_id}."""

import pytest
from test_cases.base import AgentTestCase
from test_cases.black_box.runner import BlackBoxCaseRunner

TEST_CASE_ID = "{case_id}"
TEST_CASE_LEVEL = "black_box"


class Test{case_id}BlackBoxCase(AgentTestCase, BlackBoxCaseRunner):
    """Test case {case_id}: Black-box test."""

    def test_black_box_case(self, agent_model, tmp_path):
        """Execute black-box test case {case_id}."""
        self.run_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            tmp_path=tmp_path,
        )
''', encoding="utf-8")

    print(f"✅ 生成测试包装器")

    # 4. 自动注册 handlers（使用启发式规则）
    handlers_path = project_root / "test_cases/black_box/scenario_handlers.py"
    handlers_content = handlers_path.read_text(encoding="utf-8")

    for case_id in case_ids:
        if f'register_case_handler("{case_id}")' in handlers_content:
            continue

        # 判断使用哪个 handler
        asset_dir = project_root / f"assets/t_series/{case_id}"
        has_business = (asset_dir / "业务准备.json").exists()

        if has_business:
            handler_name = "_state_handler"
        else:
            handler_name = "_generic_expected_result_handler"

        # 在文件末尾添加注册
        if not handlers_content.endswith('\n'):
            handlers_content += '\n'
        handlers_content += f'register_case_handler("{case_id}")({handler_name})\n'

    handlers_path.write_text(handlers_content, encoding="utf-8")
    print(f"✅ 注册 handlers")

    # 5. Git 提交
    run_cmd(
        ["git", "add",
         "assets/t_series/",
         "configs/black_box_t_series.json",
         "test_cases/black_box/test_t*.py",
         "test_cases/black_box/scenario_handlers.py"],
        "暂存文件"
    )

    run_cmd(
        ["git", "commit", "-m", f"feat(black_box): onboard T-series Batch {batch_num}"],
        f"提交 Batch {batch_num}"
    )

    print(f"\n✅ Batch {batch_num} 完成\n")
    return True


def main():
    # 读取批次计划
    plan_path = Path(__file__).parent.parent / "T_SERIES_ONBOARDING_PLAN.md"
    plan_text = plan_path.read_text()

    # 提取批次 3-37
    batches = []
    for batch_num in range(3, 38):
        marker = f"#### Batch {batch_num}"
        if marker not in plan_text:
            continue

        section = plan_text.split(marker)[1].split("####")[0]
        for line in section.splitlines():
            if line.startswith("**用例列表**"):
                case_ids_str = line.split(":", 1)[1].strip()
                case_ids = [cid.strip() for cid in case_ids_str.split(",")]
                batches.append((batch_num, case_ids))
                break

    print(f"找到 {len(batches)} 个批次待处理\n")

    for batch_num, case_ids in batches:
        if not process_batch(batch_num, case_ids):
            print(f"❌ Batch {batch_num} 失败，停止")
            return 1

    print(f"\n{'='*60}")
    print(f"✅ 所有批次处理完成")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
