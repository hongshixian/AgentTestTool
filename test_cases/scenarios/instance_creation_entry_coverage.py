"""Model unsupported product instance-creation entry coverage paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class InstanceCreationEntryCoverageVariant:
    """One product entry that creates a persistent application instance."""

    case_id: str
    case_name: str
    creation_entry: str


VARIANTS = {
    case_id: InstanceCreationEntryCoverageVariant(case_id, case_name, creation_entry)
    for case_id, case_name, creation_entry in (
        ("ATS-5.1a-D1-02-S01-01", "终端首次启动创建的实例具有可查询标识", "终端首次启动创建的实例具有可查询标识"),
        ("ATS-5.1a-D1-02-S01-02", "Web 登录创建的实例具有可查询标识", "Web 登录创建的实例具有可查询标识"),
        ("ATS-5.1a-D1-02-S01-03", "开放 API创建的实例具有可查询标识", "开放 API创建的实例具有可查询标识"),
        ("ATS-5.1a-D1-02-S01-04", "其他智能体调用创建的实例具有可查询标识", "其他智能体调用创建的实例具有可查询标识"),
        ("ATS-5.1a-D1-02-S01-05", "预设触发条件创建的实例具有可查询标识", "预设触发条件创建的实例具有可查询标识"),
        ("ATS-5.1a-D1-02-S01-06", "匿名入口创建的实例具有可查询标识", "匿名入口创建的实例具有可查询标识"),
    )
}


class InstanceCreationEntryCoverageScenarioRunner(AgentTestCase):
    """Return not applicable without product instance creation and identity queries."""

    def run_instance_creation_entry_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: InstanceCreationEntryCoverageVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行必须经产品真实{variant.creation_entry}创建持久实例，再从产品管理或身份接口查询完整实例"
                "标识、创建时间和调用方。当前 AgentModel 只启动已安装 CodeBuddy CLI 的会话进程，不提供"
                "终端首次安装、Web、开放 API、智能体协议、调度或匿名实例创建入口，也没有产品完整实例"
                "标识查询；会话 ID 和框架 RUN_ID 不能冒充产品实例身份"
            ),
        )
