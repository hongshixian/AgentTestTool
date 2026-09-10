"""Shared delegation from a mother case to one representative child path."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.base import AgentTestCase


_TEST_CASES_ROOT = Path(__file__).resolve().parents[1]
_SUPPORTED_FIXTURES = frozenset(
    {"agent_model", "judge_model", "request", "repeat_index"}
)


class MotherCaseScenarioRunner(AgentTestCase):
    """Execute an existing expanded child case as the representative path."""

    def run_representative_case(
        self,
        *,
        source_case_id: str,
        representative_child_id: str,
        representative_script: str,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        test_class, test_method = self._resolve_representative(
            representative_script,
            representative_child_id,
        )
        agent_model.environment.ledger.record(
            "pytest",
            "mother_case_representative_started",
            {
                "source_case_id": source_case_id,
                "representative_child_id": representative_child_id,
                "representative_script": representative_script,
            },
        )
        available: dict[str, Any] = {
            "agent_model": agent_model,
            "judge_model": judge_model,
            "request": request,
            "repeat_index": repeat_index,
        }
        parameters = inspect.signature(test_method).parameters
        fixture_names = tuple(name for name in parameters if name != "self")
        unsupported = sorted(set(fixture_names) - _SUPPORTED_FIXTURES)
        if unsupported:
            raise RuntimeError(
                "代表子用例使用了母用例执行器不支持的 fixture："
                + "、".join(unsupported)
            )
        test_method(test_class(), **{name: available[name] for name in fixture_names})

    @staticmethod
    def _resolve_representative(
        representative_script: str,
        representative_child_id: str,
    ) -> tuple[type, Any]:
        relative = Path(representative_script)
        if (
            relative.is_absolute()
            or relative.parent != Path("test_cases")
            or not relative.name.startswith("test_")
            or relative.suffix != ".py"
        ):
            raise ValueError(f"代表子用例脚本路径无效：{representative_script}")
        resolved = (Path(__file__).resolve().parents[2] / relative).resolve()
        if not resolved.is_file() or resolved.parent != _TEST_CASES_ROOT:
            raise ValueError(f"代表子用例脚本不存在：{representative_script}")

        module = importlib.import_module(f"test_cases.{resolved.stem}")
        actual_case_id = str(getattr(module, "TEST_CASE_ID", "") or "").strip()
        if actual_case_id != representative_child_id:
            raise ValueError(
                "代表子用例 ID 与脚本不匹配："
                f"期望 {representative_child_id}，实际 {actual_case_id or '<missing>'}"
            )
        test_classes = [
            value
            for value in vars(module).values()
            if inspect.isclass(value)
            and value.__module__ == module.__name__
            and value.__name__.startswith("Test")
        ]
        methods = [
            (test_class, method)
            for test_class in test_classes
            for name, method in vars(test_class).items()
            if name.startswith("test_") and callable(method)
        ]
        if len(methods) != 1:
            raise ValueError(
                f"代表子用例脚本必须恰好包含一个测试方法：{representative_script}"
            )
        return methods[0]
