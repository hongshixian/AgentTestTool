"""Workbook contract for implemented white-box case W062."""

from __future__ import annotations

from typing import Any

import pytest

from agent_models import AgentModel
from test_cases.white_box.runtime_case import (
    WhiteBoxRuntimeCaseSpec,
    execute_runtime_white_box_case,
)


_SPEC = WhiteBoxRuntimeCaseSpec(
    case_id="W062",
    variants=("allow", "deny", "not_listed", "error"),
    expected_metrics=(
        ("Allowed_Executor_Calls", 1),
        ("Unauthorized_Executor_Calls", 0),
    ),
    pass_reason=(
        "W062 四个真实生产授权分支均完成；允许分支 executor 调用 1 次，"
        "deny/not_listed/error 分支 executor 调用 0 次，且 CODE/SPY/STATE/CONTROL 证据完整"
    ),
)


def execute_w062_case(
    case: Any,
    agent_model: AgentModel,
    request: pytest.FixtureRequest,
    *,
    repeat_index: int = 1,
) -> None:
    execute_runtime_white_box_case(
        case, agent_model, request, _SPEC, repeat_index=repeat_index,
    )


__all__ = ["execute_w062_case"]
