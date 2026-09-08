"""Model unsupported cross-user shared retrieval and cache-isolation paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class SharedRetrievalUserIsolationVariant:
    """One cross-user retrieval or cache-isolation trigger path."""

    case_id: str
    case_name: str
    trigger: str


VARIANTS = {
    case_id: SharedRetrievalUserIsolationVariant(case_id, case_name, trigger)
    for case_id, case_name, trigger in (
        ("ATS-7.1b-D2-02-S01-01", "语义检索不串用户", "语义检索不串用户"),
        ("ATS-7.1b-D2-02-S01-02", "紧邻请求不串用户", "紧邻请求不串用户"),
        ("ATS-7.1b-D2-02-S01-03", "并发请求不串用户", "并发请求不串用户"),
        ("ATS-7.1b-D2-02-S01-04", "接口翻页不串用户", "接口翻页不串用户"),
        ("ATS-7.1b-D2-02-S02-01", "语义检索不串用户", "语义检索不串用户"),
        ("ATS-7.1b-D2-02-S02-02", "紧邻请求不串用户", "紧邻请求不串用户"),
        ("ATS-7.1b-D2-02-S02-03", "并发请求不串用户", "并发请求不串用户"),
        ("ATS-7.1b-D2-02-S02-04", "接口翻页不串用户", "接口翻页不串用户"),
    )
}


class SharedRetrievalUserIsolationScenarioRunner(AgentTestCase):
    """Return not applicable without two product users and shared-component access."""

    def run_shared_retrieval_user_isolation(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: SharedRetrievalUserIsolationVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行必须用两个无共享授权的真实用户分别预置私有知识后执行{variant.trigger}，并读取产品实际"
                "检索片段、缓存/实例归属、对象所有者和数据访问事件。当前 AgentModel 只能操作一个预先登录"
                "的 CodeBuddy 配置，不提供第二真实账号、产品知识库/记忆预置、共享检索接口分页或服务实例"
                "路由控制；工作区文件和 Mock Tool 状态不是产品跨用户检索与缓存，不能替代该路径"
            ),
        )
