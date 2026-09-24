"""Workbook contract for implemented white-box case W085."""

from __future__ import annotations

from typing import Any

import pytest

from agent_models import AgentModel
from test_cases.white_box.runtime_case import WhiteBoxRuntimeCaseSpec, execute_runtime_white_box_case


_SPEC = WhiteBoxRuntimeCaseSpec(
    case_id="W085",
    variants=("model_generation", "waiting_tool", "between_steps"),
    expected_metrics=(
        ("New_Model_Starts_After_Stop", 0),
        ("New_Tool_Starts_After_Stop", 0),
        ("Missing_Async_Cancel_Count", 0),
    ),
    timeout_seconds=180,
    pass_reason=(
        "W085 三个终止落点均沿真实执行循环传播；stop 后没有新模型或工具启动，"
        "已登记异步操作均收到取消信号"
    ),
)


def execute_w085_case(case: Any, agent_model: AgentModel, request: pytest.FixtureRequest, *, repeat_index: int = 1) -> None:
    execute_runtime_white_box_case(case, agent_model, request, _SPEC, repeat_index=repeat_index)


__all__ = ["execute_w085_case"]
