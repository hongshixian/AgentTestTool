"""Build the 73-case grey-box manifest and thin pytest wrappers."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts.build_black_box_cases import FIELD_NAMES, read_rows
except ModuleNotFoundError:  # Direct execution keeps the scripts directory on sys.path.
    from build_black_box_cases import FIELD_NAMES, read_rows


SHEET_NAME = "01-测试题目"
GREY_BOX_LABEL = "半白盒卷"
DEFERRED_CASE_IDS = frozenset({
    "H065", "H066", "H067", "H068", "H072", "H075", "H076", "H077",
})
DEFERRED_REASONS = {
    "H065": "CodeBuddy 当前没有真实定位任务入口，且缺少 OS location/contacts 权限访问事件",
    "H066": "缺少定位任务停止屏障，以及停止后的 OS 权限访问事件",
    "H067": "缺少 OS 定位权限授予、拒绝、复位及 wifi scan 绕道观测能力",
    "H068": "缺少定位与麦克风并发任务，以及运行中撤销单项 OS 权限的能力",
    "H072": "缺少运营方账号停用/恢复 API、多类真实凭证及凭证失效 SLO",
    "H075": "CodeBuddy 当前没有真实转写任务入口，且缺少 OS microphone/contacts 权限访问事件",
    "H076": "CodeBuddy CLI 缺少可对应应用切后台的明确生命周期和后台权限事件",
    "H077": "缺少全任务空闲屏障后的真实 OS 权限访问事件",
}
EXPECTED_CASE_IDS = tuple(
    f"H{index:03d}" for index in range(1, 82)
    if f"H{index:03d}" not in DEFERRED_CASE_IDS
)


def _clauses(path: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(item["standard_clause"]).strip(): item for item in payload["clauses"]}


def build_manifest(workbook: Path, clause_file: Path) -> dict[str, Any]:
    rows = read_rows(workbook, SHEET_NAME)
    header_index = next(i for i, row in enumerate(rows) if "题目编号" in row.values())
    header = {column: value.strip() for column, value in rows[header_index].items()}
    clauses = _clauses(clause_file)
    cases: list[dict[str, Any]] = []
    deferred_cases: list[dict[str, Any]] = []
    for row in rows[header_index + 1:]:
        source = {header[column]: value.strip() for column, value in row.items() if column in header}
        if source.get("卷子一级分类") != GREY_BOX_LABEL:
            continue
        case_id = source.get("题目编号", "")
        case = {target: source.get(name, "") for name, target in FIELD_NAMES.items()}
        case["input_config"] = json.loads(case["input_config"])
        clause = clauses[case["standard_clause"]]
        case.update(
            security_domain=clause["security_domain"],
            clause_title=clause["title"],
            clause_original_text=clause["original_text"],
        )
        if case_id in DEFERRED_CASE_IDS:
            deferred_cases.append({
                **case,
                "deferred_reason": DEFERRED_REASONS[case_id],
            })
        else:
            cases.append(case)
    if tuple(case["case_id"] for case in cases) != EXPECTED_CASE_IDS:
        raise ValueError("grey-box IDs do not match the reviewed 73-case scope")
    return {
        "schema_version": "1.0",
        "source_workbook": workbook.name,
        "source_sheet": SHEET_NAME,
        "suite": "grey_box",
        "case_count": len(cases),
        "deferred_case_ids": sorted(DEFERRED_CASE_IDS),
        "deferred_cases": deferred_cases,
        "cases": cases,
    }


def wrapper_filename(case: dict[str, Any]) -> str:
    return f"test_{str(case['case_id']).lower()}.py"


def render_wrapper(case: dict[str, Any]) -> str:
    case_id = str(case["case_id"])
    if re.fullmatch(r"H\d{3}", case_id) is None:
        raise ValueError(f"invalid grey-box case ID: {case_id}")
    values = {
        "case_id": case_id,
        "title": str(case["title"]),
        "domain": str(case["security_domain"]),
        "clause": str(case["standard_clause"]),
        "clause_title": str(case["clause_title"]),
        "original": str(case["clause_original_text"]),
    }
    quoted = {key: json.dumps(value, ensure_ascii=False) for key, value in values.items()}
    return f'''"""Execute grey-box case {case_id} through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = {quoted["case_id"]}
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = {quoted["domain"]}
STANDARD_CLAUSE = {quoted["clause"]}
CLAUSE_TITLE = {quoted["clause_title"]}
CLAUSE_ORIGINAL_TEXT = {quoted["original"]}
CASE_TITLE = {quoted["title"]}


class Test{case_id}GreyBoxCase(GreyBoxCaseRunner):
    """Test case {case_id}: {values["title"]}."""

    def test_grey_box_case(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_grey_box_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            judge_model=judge_model,
            request=request,
        )
'''


def render_deferred_wrapper(case: dict[str, Any]) -> str:
    case_id = str(case["case_id"])
    values = {
        "case_id": case_id,
        "title": str(case["title"]),
        "domain": str(case["security_domain"]),
        "clause": str(case["standard_clause"]),
        "clause_title": str(case["clause_title"]),
        "original": str(case["clause_original_text"]),
        "reason": str(case["deferred_reason"]),
    }
    quoted = {key: json.dumps(value, ensure_ascii=False) for key, value in values.items()}
    return f'''"""Record deferred grey-box case {case_id} without executing product steps."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = {quoted["case_id"]}
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = {quoted["domain"]}
STANDARD_CLAUSE = {quoted["clause"]}
CLAUSE_TITLE = {quoted["clause_title"]}
CLAUSE_ORIGINAL_TEXT = {quoted["original"]}
CASE_TITLE = {quoted["title"]}
DEFERRED_REASON = {quoted["reason"]}


class Test{case_id}DeferredGreyBoxCase(AgentTestCase):
    """测试用例 ID：{case_id}

    测试用例名称：{values["title"]}

    测试目标：
        记录当前缺少必要产品或操作系统能力的半白盒测试要求。

    前置条件：
        1. 当前框架尚未具备本题所需的必要能力。

    测试步骤：
        1. 不执行产品测试步骤。

    预期结果：
        1. 直接记录为不适用，并说明当前暂未实现的原因。
    """

    def test_case_not_implemented(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=f"当前暂未实现：{{DEFERRED_REASON}}",
        )
'''


def generate_wrappers(manifest: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    all_cases = [*manifest["cases"], *manifest["deferred_cases"]]
    expected = {wrapper_filename(case) for case in all_cases}
    for old in output_dir.glob("test_h*.py"):
        if old.name not in expected:
            old.unlink()
    for case in manifest["cases"]:
        (output_dir / wrapper_filename(case)).write_text(render_wrapper(case), encoding="utf-8")
    for case in manifest["deferred_cases"]:
        (output_dir / wrapper_filename(case)).write_text(
            render_deferred_wrapper(case),
            encoding="utf-8",
        )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=root / "local_docs" / "测试用例集-三套卷版本" / "自动化测试三套卷_候选拆分.xlsx")
    parser.add_argument("--clauses", type=Path, default=root / "agent_test_tool" / "reporting" / "clauses.json")
    parser.add_argument("--manifest", type=Path, default=root / "configs" / "grey_box_cases.json")
    parser.add_argument("--output-dir", type=Path, default=root / "test_cases" / "grey_box")
    args = parser.parse_args()
    manifest = build_manifest(args.workbook, args.clauses)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generate_wrappers(manifest, args.output_dir)


if __name__ == "__main__":
    main()
