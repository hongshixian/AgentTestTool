"""Generate thin mother-case wrappers for explicitly delegated manifest entries."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def wrapper_filename(case: dict[str, Any]) -> str:
    """Return a stable English filename derived from the representative script."""

    representative = Path(str(case["representative_child_script"]))
    stem = representative.stem.removeprefix("test_")
    return f"test_mother_{stem}.py"


def render_wrapper(case: dict[str, Any]) -> str:
    """Render one delegate wrapper while rejecting unfinished case definitions."""

    source_case_id = str(case.get("source_case_id", "")).strip()
    if case.get("implementation_mode") != "delegate":
        raise ValueError(f"{source_case_id} is not explicitly marked for delegation")
    representative_id = str(case.get("representative_child_id", "")).strip()
    representative_script = str(case.get("representative_child_script", "")).strip()
    if not source_case_id.startswith("TC-") or not representative_id or not representative_script:
        raise ValueError("delegate wrapper requires mother ID, child ID, and child script")
    selected = {
        (child.get("case_id"), child.get("script"))
        for child in case.get("representative_child_candidates", [])
    }
    if (representative_id, representative_script) not in selected:
        raise ValueError(f"{source_case_id} representative child is not a candidate")

    normalized_id = re.sub(r"[^A-Za-z0-9]", "", source_case_id).upper()
    name = str(case.get("name", "")).strip()
    category = str(case.get("category", "")).strip()
    priority = str(case.get("priority", "")).strip()
    if not name or not category or not priority:
        raise ValueError(f"{source_case_id} is missing wrapper metadata")

    return f'''"""Run one representative path for mother case {source_case_id}."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.mother_cases.base import MotherCaseScenarioRunner


pytestmark = [pytest.mark.e2e, pytest.mark.mother_case]
TEST_CASE_ID = {_quoted(source_case_id)}
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = {_quoted(source_case_id)}
REPRESENTATIVE_CHILD_ID = {_quoted(representative_id)}
REPRESENTATIVE_CHILD_SCRIPT = {_quoted(representative_script)}
CLI_CATEGORY = {_quoted(category)}
EXECUTION_PRIORITY = {_quoted(priority)}


class Test{normalized_id}MotherCase(MotherCaseScenarioRunner):
    """测试用例 ID：{source_case_id}

    测试用例名称：{name}

    测试目标：
        验证母用例的一条明确代表路径，并保留母用例与子用例的关联。

    前置条件：
        1. 被测 Agent CLI 已安装并完成专用测试身份认证。
        2. 代表子用例所需的测试能力和隔离环境已经配置。

    测试步骤：
        1. 记录母用例、代表子用例和脚本的关联信息。
        2. 执行选定的代表子用例路径。
        3. 原样记录代表路径产生的四态测评结论。

    预期结果：
        1. 代表路径有效执行并显式产生四态结论之一。
        2. 报告明确限定为本条母用例的代表路径覆盖。
    """

    def test_representative_child_path(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        self.run_representative_case(
            source_case_id=SOURCE_CASE_ID,
            representative_child_id=REPRESENTATIVE_CHILD_ID,
            representative_script=REPRESENTATIVE_CHILD_SCRIPT,
            agent_model=agent_model,
            judge_model=judge_model,
            request=request,
            repeat_index=repeat_index,
        )
'''


def generate_wrappers(manifest: dict[str, Any], output_dir: Path) -> tuple[Path, ...]:
    """Write wrappers only for entries whose implementation mode is delegate."""

    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("manifest cases must be a list")
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    seen_names: set[str] = set()
    for case in cases:
        if case.get("implementation_mode") != "delegate":
            continue
        filename = wrapper_filename(case)
        if filename in seen_names:
            raise ValueError(f"duplicate generated wrapper filename: {filename}")
        seen_names.add(filename)
        path = output_dir / filename
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
        "--manifest",
        type=Path,
        default=root / "configs" / "mother_cases_v3.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    generated = generate_wrappers(manifest, args.output_dir)
    print(json.dumps({"generated_count": len(generated)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
