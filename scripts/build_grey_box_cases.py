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
    for row in rows[header_index + 1:]:
        source = {header[column]: value.strip() for column, value in row.items() if column in header}
        if source.get("卷子一级分类") != GREY_BOX_LABEL:
            continue
        case_id = source.get("题目编号", "")
        if case_id in DEFERRED_CASE_IDS:
            continue
        case = {target: source.get(name, "") for name, target in FIELD_NAMES.items()}
        case["input_config"] = json.loads(case["input_config"])
        clause = clauses[case["standard_clause"]]
        case.update(
            security_domain=clause["security_domain"],
            clause_title=clause["title"],
            clause_original_text=clause["original_text"],
        )
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


def generate_wrappers(manifest: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = {wrapper_filename(case) for case in manifest["cases"]}
    for old in output_dir.glob("test_h*.py"):
        if old.name not in expected:
            old.unlink()
    for case in manifest["cases"]:
        (output_dir / wrapper_filename(case)).write_text(render_wrapper(case), encoding="utf-8")


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
