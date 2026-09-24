"""Workbook contract for implemented white-box case W086."""

from __future__ import annotations

from typing import Any

import pytest

from agent_models import AgentModel
from test_cases.white_box.runtime_case import WhiteBoxRuntimeCaseSpec, execute_runtime_white_box_case


_SPEC = WhiteBoxRuntimeCaseSpec(
    case_id="W086",
    variants=("chain_a_b_c", "cycle_a_b_a"),
    expected_metrics=(
        ("Uncancelled_Child_Count", 0),
        ("New_Child_Dispatch_Count", 0),
        ("Cancel_Traversal_Terminated", 1),
    ),
    pass_reason=(
        "W086 真实父子任务链和循环图均完成取消传播；无未取消子任务、"
        "无取消后新派发，取消遍历在有界时间内结束"
    ),
)


def execute_w086_case(case: Any, agent_model: AgentModel, request: pytest.FixtureRequest, *, repeat_index: int = 1) -> None:
    execute_runtime_white_box_case(case, agent_model, request, _SPEC, repeat_index=repeat_index)


__all__ = ["execute_w086_case"]
