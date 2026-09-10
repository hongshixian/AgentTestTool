"""Generate deferred P3 mother-case wrappers from the v3 manifest."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping


EXPECTED_P3_CASE_COUNT = 60
SUPPORTED_PROFILES = frozenset(
    {
        "instance_api",
        "product_audit",
        "material",
        "component_loader",
        "extension_loader",
        "device_ui",
        "route_observation",
        "risk_action",
    }
)


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _required_text(case: Mapping[str, Any], field: str) -> str:
    value = str(case.get(field) or "").strip()
    if not value:
        raise ValueError(f"{case.get('source_case_id')} is missing {field}")
    return value


def wrapper_filename(source_case_id: str) -> str:
    """Return the standard one-file-per-source-case wrapper name."""

    normalized = re.sub(r"[^a-z0-9]+", "_", source_case_id.lower()).strip("_")
    return f"test_{normalized}.py"


def execution_profile(case: Mapping[str, Any]) -> str:
    """Derive the stable deferred profile from the capability key."""

    source_case_id = _required_text(case, "source_case_id")
    if source_case_id == "TC-5.4c-D3-01":
        return "extension_loader"
    capability = _required_text(case, "required_capability")
    profile = capability.split("：", maxsplit=1)[0].strip()
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"{source_case_id} has unsupported P3 profile: {profile}")
    return profile


def representative_child(case: Mapping[str, Any]) -> tuple[str, str]:
    """Select the first P3/E candidate and leave audited P3/F rows empty."""

    source_case_id = _required_text(case, "source_case_id")
    category = _required_text(case, "category")
    if category == "F":
        return "", ""
    if category != "E":
        raise ValueError(f"{source_case_id} is not a P3 E/F case")

    candidates = case.get("representative_child_candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError(f"{source_case_id} has no representative child candidate")
    selected = candidates[0]
    if not isinstance(selected, Mapping):
        raise ValueError(f"{source_case_id} has an invalid child candidate")
    child_id = _required_text(selected, "case_id")
    child_script = _required_text(selected, "script")
    available = {
        (
            str(candidate.get("case_id") or "").strip(),
            str(candidate.get("script") or "").strip(),
        )
        for candidate in candidates
        if isinstance(candidate, Mapping)
    }
    if (child_id, child_script) not in available:
        raise ValueError(f"{source_case_id} selected child is not a candidate")
    return child_id, child_script


def render_wrapper(case: Mapping[str, Any]) -> str:
    """Render one thin wrapper for the shared deferred P3 runner."""

    source_case_id = _required_text(case, "source_case_id")
    if _required_text(case, "priority") != "P3":
        raise ValueError(f"{source_case_id} is not a P3 case")
    category = _required_text(case, "category")
    if category not in {"E", "F"}:
        raise ValueError(f"{source_case_id} is not a P3 E/F case")

    name = _required_text(case, "name")
    required_capability = _required_text(case, "required_capability")
    profile = execution_profile(case)
    child_id, child_script = representative_child(case)
    normalized_id = re.sub(r"[^A-Za-z0-9]", "", source_case_id).upper()

    return f'''"""Run the deferred P3 mother case {source_case_id}."""

import pytest

from agent_models import AgentModel
from test_cases.mother_cases.p3_deferred import P3DeferredMotherCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.mother_case]
TEST_CASE_ID = {_quoted(source_case_id)}
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = {_quoted(source_case_id)}
REPRESENTATIVE_CHILD_ID = {_quoted(child_id)}
REPRESENTATIVE_CHILD_SCRIPT = {_quoted(child_script)}
PRIORITY = "P3"
CATEGORY = {_quoted(category)}
IMPLEMENTATION_MODE = "deferred"
REQUIRED_CAPABILITY = {_quoted(required_capability)}
EXECUTION_PROFILE = {_quoted(profile)}


class Test{normalized_id}P3Deferred(P3DeferredMotherCaseRunner):
    """测试用例 ID：{source_case_id}

    测试用例名称：{name}

    测试目标：
        按 CLI 宽松判定版记录本轮暂缓原因和重新纳入所需条件。

    前置条件：
        1. 母用例 manifest 已声明本条 P3 用例及必需能力。
        2. 不使用 Agent 自述或测试侧模拟物替代缺失的真实能力。

    测试步骤：
        1. 校验母用例优先级、类别和稳定执行 profile。
        2. 记录代表子用例追溯信息和当前缺失能力。
        3. 显式返回本轮不适用结论，不调用真实产品服务。

    预期结果：
        1. 报告准确记录本轮暂缓，不产生虚假的通过或不通过结论。
        2. 结论不被解释为原条款对产品整体不适用。
    """

    def test_deferred_mother_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_p3_deferred_case(
            source_case_id=SOURCE_CASE_ID,
            profile=EXECUTION_PROFILE,
            agent_model=agent_model,
            request=request,
        )
'''


def generate_wrappers(
    manifest: Mapping[str, Any],
    output_dir: Path,
) -> tuple[Path, ...]:
    """Write all P3 wrappers while protecting unrelated existing files."""

    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("manifest cases must be a list")
    selected = [case for case in cases if case.get("priority") == "P3"]
    if len(selected) != EXPECTED_P3_CASE_COUNT:
        raise ValueError(
            f"expected {EXPECTED_P3_CASE_COUNT} P3 cases, found {len(selected)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    seen_names: set[str] = set()
    for case in selected:
        source_case_id = _required_text(case, "source_case_id")
        filename = wrapper_filename(source_case_id)
        if filename in seen_names:
            raise ValueError(f"duplicate generated wrapper filename: {filename}")
        seen_names.add(filename)
        path = output_dir / filename
        if path.exists() and 'PRIORITY = "P3"' not in path.read_text(encoding="utf-8"):
            raise FileExistsError(f"refusing to overwrite non-P3 wrapper: {path}")
        path.write_text(render_wrapper(case), encoding="utf-8")
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
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "test_cases" / "mother_cases",
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    generated = generate_wrappers(manifest, args.output_dir)
    print(json.dumps({"generated_count": len(generated)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
