"""Build the black-box case manifest and thin pytest wrappers from the workbook."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any


SHEET_NAME = "01-测试题目"
BLACK_BOX_LABEL = "黑盒卷"
EXPECTED_CASE_IDS = tuple(f"B{index:03d}" for index in range(1, 43))
FIELD_NAMES = {
    "题目编号": "case_id",
    "卷子一级分类": "suite",
    "卷子二级分类": "evidence_scope",
    "题目名称": "title",
    "对应条款": "standard_clause",
    "T1 前置条件": "preconditions",
    "T2 具体测试操作": "steps",
    "T3 判断方式（Pass / Fail）": "verdict_expression",
    "描述性判断方式（通过／不通过）": "verdict_description",
    "测试输入与变体": "variants",
    "输入配置JSON示例": "input_config",
    "必需原始证据字段": "required_evidence",
    "原始证据字段示例": "evidence_example",
    "输入字段类型与示例": "input_schema",
    "判定指标计算规则": "metric_rules",
    "观测JSON示例（通过样本）": "passing_observation",
    "Fail判据（逐项反例）": "failure_examples",
    "证据不足与接入未就绪": "readiness_policy",
    "必需接入能力": "required_capabilities",
    "证据来源": "evidence_sources",
    "判定边界": "boundary",
    "清理与复位": "cleanup",
    "自动化条件": "automation_condition",
    "执行状态": "execution_status",
}
XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {
    "r": "http://schemas.openxmlformats.org/package/2006/relationships",
    "o": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _column(reference: str) -> str:
    match = re.match(r"[A-Z]+", reference)
    if match is None:
        raise ValueError(f"invalid cell reference: {reference}")
    return match.group()


def _shared_strings(archive: zipfile.ZipFile) -> tuple[str, ...]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return ()
    return tuple(
        "".join(node.text or "" for node in item.findall(".//x:t", XML_NS))
        for item in root.findall("x:si", XML_NS)
    )


def _cell_text(cell: ET.Element, shared: tuple[str, ...]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//x:t", XML_NS))
    value = cell.find("x:v", XML_NS)
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        return shared[int(value.text)]
    return value.text


def _sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        relation.get("Id"): relation.get("Target")
        for relation in relationships.findall("r:Relationship", REL_NS)
    }
    for sheet in workbook.findall(".//x:sheet", XML_NS):
        if sheet.get("name") != sheet_name:
            continue
        relation_id = sheet.get(f"{{{REL_NS['o']}}}id")
        target = targets.get(relation_id)
        if target is None:
            break
        normalized = target.lstrip("/")
        return normalized if normalized.startswith("xl/") else f"xl/{normalized}"
    raise ValueError(f"workbook does not contain sheet {sheet_name!r}")


def read_rows(workbook: Path, sheet_name: str = SHEET_NAME) -> tuple[dict[str, str], ...]:
    """Read one worksheet using only XLSX's ZIP and XML representation."""

    with zipfile.ZipFile(workbook) as archive:
        shared = _shared_strings(archive)
        root = ET.fromstring(archive.read(_sheet_path(archive, sheet_name)))
    rows: list[dict[str, str]] = []
    for row in root.findall(".//x:sheetData/x:row", XML_NS):
        rows.append(
            {
                _column(cell.get("r", "")): _cell_text(cell, shared)
                for cell in row.findall("x:c", XML_NS)
            }
        )
    return tuple(rows)


def _clause_map(clause_file: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(clause_file.read_text(encoding="utf-8"))
    return {
        str(item["standard_clause"]).strip(): item
        for item in payload.get("clauses", [])
    }


def build_manifest(workbook: Path, clause_file: Path) -> dict[str, Any]:
    """Return a validated, portable manifest for all black-box workbook rows."""

    rows = read_rows(workbook)
    header_index = next(
        (index for index, row in enumerate(rows) if "题目编号" in row.values()),
        None,
    )
    if header_index is None:
        raise ValueError("test-case header row was not found")
    header = {column: value.strip() for column, value in rows[header_index].items()}
    missing = set(FIELD_NAMES) - set(header.values())
    if missing:
        raise ValueError(f"workbook is missing required columns: {sorted(missing)}")
    clauses = _clause_map(clause_file)
    cases: list[dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        source = {header[column]: value.strip() for column, value in row.items() if column in header}
        if source.get("卷子一级分类") != BLACK_BOX_LABEL:
            continue
        case = {target: source.get(source_name, "") for source_name, target in FIELD_NAMES.items()}
        try:
            case["input_config"] = json.loads(case["input_config"])
        except json.JSONDecodeError as error:
            raise ValueError(f"{case['case_id']} has invalid input JSON") from error
        if not isinstance(case["input_config"], dict):
            raise ValueError(f"{case['case_id']} input JSON must be an object")
        clause = clauses.get(case["standard_clause"])
        if clause is None:
            raise ValueError(f"{case['case_id']} has unknown clause {case['standard_clause']!r}")
        case.update(
            security_domain=clause["security_domain"],
            clause_title=clause["title"],
            clause_original_text=clause["original_text"],
        )
        cases.append(case)
    if tuple(case["case_id"] for case in cases) != EXPECTED_CASE_IDS:
        raise ValueError("black-box case IDs must be exactly B001 through B042 in order")
    for case in cases:
        if case["input_config"].get("Case_ID") != case["case_id"]:
            raise ValueError(f"{case['case_id']} input JSON Case_ID does not match")
        if "Pass" not in case["verdict_expression"] or "Fail" not in case["verdict_expression"]:
            raise ValueError(f"{case['case_id']} lacks an explicit Pass/Fail expression")
    return {
        "schema_version": "1.0",
        "source_workbook": workbook.name,
        "source_sheet": SHEET_NAME,
        "suite": "black_box",
        "case_count": len(cases),
        "cases": cases,
    }


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def wrapper_filename(case: dict[str, Any]) -> str:
    return f"test_{str(case['case_id']).lower()}.py"


def render_wrapper(case: dict[str, Any]) -> str:
    """Render one thin wrapper whose behavior remains in BlackBoxCaseRunner."""

    case_id = str(case["case_id"])
    if not re.fullmatch(r"B\d{3}", case_id):
        raise ValueError(f"invalid black-box case ID: {case_id!r}")
    title = str(case["title"])
    return f'''"""Execute black-box case {case_id} through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = {_quoted(case_id)}
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = {_quoted(str(case["security_domain"]))}
STANDARD_CLAUSE = {_quoted(str(case["standard_clause"]))}
CLAUSE_TITLE = {_quoted(str(case["clause_title"]))}
CLAUSE_ORIGINAL_TEXT = {_quoted(str(case["clause_original_text"]))}
CASE_TITLE = {_quoted(title)}


class Test{case_id}BlackBoxCase(BlackBoxCaseRunner):
    """Test case {case_id}: {title}."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_black_box_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            request=request,
        )
'''


def generate_wrappers(manifest: dict[str, Any], output_dir: Path) -> tuple[Path, ...]:
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("manifest cases must be a list")
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for case in cases:
        path = output_dir / wrapper_filename(case)
        content = render_wrapper(case)
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite non-matching wrapper: {path}")
        path.write_text(content, encoding="utf-8")
        generated.append(path)
    return tuple(generated)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=root / "local_docs" / "测试用例集-三套卷版本" / "自动化测试三套卷_候选拆分.xlsx",
    )
    parser.add_argument(
        "--clauses",
        type=Path,
        default=root / "agent_test_tool" / "reporting" / "clauses.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=root / "configs" / "black_box_cases.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "test_cases" / "black_box",
    )
    args = parser.parse_args()

    manifest = build_manifest(args.workbook, args.clauses)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    generated = generate_wrappers(manifest, args.output_dir)
    print(json.dumps({"case_count": len(generated)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
