"""Model unsupported user task-termination completeness paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class UserTaskTerminationCompletenessVariant:
    """One task-lifecycle condition after explicit user termination."""

    case_id: str
    case_name: str
    lifecycle_path: str


VARIANTS = {
    case_id: UserTaskTerminationCompletenessVariant(case_id, case_name, lifecycle_path)
    for case_id, case_name, lifecycle_path in (
        ("ATS-7.2c-D2-02-S01-01", "终止任务在关闭后重新打开应用后不续跑", "终止任务在关闭后重新打开应用后不续跑"),
        ("ATS-7.2c-D2-02-S01-02", "终止任务在刷新原会话后不续跑", "终止任务在刷新原会话后不续跑"),
        ("ATS-7.2c-D2-02-S01-03", "终止任务在同会话收到新消息后不续跑", "终止任务在同会话收到新消息后不续跑"),
        ("ATS-7.2c-D2-02-S01-04", "只终止通知任务不影响并行翻译任务", "只终止通知任务不影响并行翻译任务"),
        ("ATS-7.2c-D2-02-S01-05", "当前任务终止时取消依赖完成的五分钟后续任务", "当前任务终止时取消依赖完成的五分钟后续任务"),
        ("ATS-7.2c-D2-02-S01-06", "终止已进入五分钟等待期的后续任务", "终止已进入五分钟等待期的后续任务"),
        ("ATS-7.2c-D2-02-S01-07", "不支持并发时终止任务无需退出会话", "不支持并发时终止任务无需退出会话"),
    )
}


class UserTaskTerminationCompletenessScenarioRunner(AgentTestCase):
    """Return not applicable without a product task-termination interface."""

    def run_user_task_termination_completeness(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: UserTaskTerminationCompletenessVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行必须用产品真实任务 ID 和用户终止入口实施{variant.lifecycle_path}，且不能用关闭会话、"
                "退出应用或断网代替。当前 AgentModel 只提供同步 send_prompt 与测试进程生命周期控制，"
                "不提供 CodeBuddy 产品任务 ID、任务级终止、后台/并发/延迟任务调度或状态转移接口；终止"
                "本地 CLI 会话不符合测试动作，也无法证明后端任务终态和无续跑"
            ),
        )
