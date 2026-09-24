"""Build the white-box manifest and deferred pytest wrappers."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts.build_black_box_cases import FIELD_NAMES, read_rows
except ModuleNotFoundError:
    from build_black_box_cases import FIELD_NAMES, read_rows


SHEET_NAME = "01-测试题目"
WHITE_BOX_LABEL = "白盒卷"
EXPECTED_CASE_IDS = tuple(f"W{index:03d}" for index in range(1, 87))
IMPLEMENTED_CASE_IDS = frozenset({"W062"})


def _clauses(path: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(item["standard_clause"]).strip(): item for item in payload["clauses"]}


def _deferred_reason(source: dict[str, str]) -> str:
    category = source.get("卷子二级分类", "")
    if "记录" in category or "字段" in category:
        return (
            "缺少与被测部署版本匹配的源码、真实记录写入与序列化实现、"
            "内部字段映射及代码调用 Spy，无法核验白盒记录要求"
        )
    return (
        "缺少与被测部署版本匹配的源码、可复现测试构建、真实生产入口、"
        "可替换内部依赖、代码调用 Spy 及控制分支清单，无法执行白盒分支核验"
    )


def build_manifest(workbook: Path, clause_file: Path) -> dict[str, Any]:
    rows = read_rows(workbook, SHEET_NAME)
    header_index = next(i for i, row in enumerate(rows) if "题目编号" in row.values())
    header = {column: value.strip() for column, value in rows[header_index].items()}
    clauses = _clauses(clause_file)
    cases: list[dict[str, Any]] = []
    for row in rows[header_index + 1:]:
        source = {
            header[column]: value.strip()
            for column, value in row.items()
            if column in header
        }
        if source.get("卷子一级分类") != WHITE_BOX_LABEL:
            continue
        case = {target: source.get(name, "") for name, target in FIELD_NAMES.items()}
        case["input_config"] = json.loads(case["input_config"])
        clause = clauses[case["standard_clause"]]
        case.update(
            security_domain=clause["security_domain"],
            clause_title=clause["title"],
            clause_original_text=clause["original_text"],
            deferred_reason=("" if source.get("题目编号") in IMPLEMENTED_CASE_IDS else _deferred_reason(source)),
        )
        cases.append(case)
    if tuple(case["case_id"] for case in cases) != EXPECTED_CASE_IDS:
        raise ValueError("white-box IDs do not match the reviewed 86-case scope")
    return {
        "schema_version": "1.0",
        "source_workbook": workbook.name,
        "source_sheet": SHEET_NAME,
        "suite": "white_box",
        "case_count": len(cases),
        "implemented_case_ids": sorted(IMPLEMENTED_CASE_IDS),
        "cases": cases,
    }


def render_wrapper(case: dict[str, Any]) -> str:
    case_id = str(case["case_id"])
    if re.fullmatch(r"W\d{3}", case_id) is None:
        raise ValueError(f"invalid white-box case ID: {case_id}")
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
    return f'''"""Record deferred white-box case {case_id} without executing product steps."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase
from test_cases.pipeline import PipelinePhase, pipeline_phase


pytestmark = [pytest.mark.e2e, pytest.mark.white_box]
TEST_CASE_ID = {quoted["case_id"]}
TEST_CASE_LEVEL = "white_box"
SECURITY_DOMAIN = {quoted["domain"]}
STANDARD_CLAUSE = {quoted["clause"]}
CLAUSE_TITLE = {quoted["clause_title"]}
CLAUSE_ORIGINAL_TEXT = {quoted["original"]}
CASE_TITLE = {quoted["title"]}
DEFERRED_REASON = {quoted["reason"]}


class Test{case_id}DeferredWhiteBoxCase(AgentTestCase):
    """测试用例 ID：{case_id}

    测试用例名称：{values["title"]}

    测试目标：
        记录当前缺少厂商源码与白盒测试构建能力的测试要求。

    前置条件：
        1. 当前第三方测评框架不具备本题所需的白盒能力。

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
        with pipeline_phase(request, agent_model, PipelinePhase.CAPABILITY_CHECK):
            self.conclude_not_applicable(
                request,
                agent_model,
                reason=f"当前暂未实现：{{DEFERRED_REASON}}",
            )
'''


def generate_wrappers(manifest: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = {f"test_{str(case['case_id']).lower()}.py" for case in manifest["cases"]}
    for old in output_dir.glob("test_w*.py"):
        if old.name not in expected:
            old.unlink()
    for case in manifest["cases"]:
        if str(case["case_id"]) in IMPLEMENTED_CASE_IDS:
            if not (output_dir / f"test_{str(case['case_id']).lower()}.py").is_file():
                raise ValueError(f"implemented white-box wrapper is missing: {case['case_id']}")
            continue
        path = output_dir / f"test_{str(case['case_id']).lower()}.py"
        path.write_text(render_wrapper(case), encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=root / "local_docs" / "测试用例集-三套卷版本" / "自动化测试三套卷_候选拆分.xlsx")
    parser.add_argument("--clauses", type=Path, default=root / "agent_test_tool" / "reporting" / "clauses.json")
    parser.add_argument("--manifest", type=Path, default=root / "configs" / "white_box_cases.json")
    parser.add_argument("--output-dir", type=Path, default=root / "test_cases" / "white_box")
    args = parser.parse_args()
    manifest = build_manifest(args.workbook, args.clauses)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generate_wrappers(manifest, args.output_dir)


if __name__ == "__main__":
    main()
