"""Model runtime authorization-scope pruning unavailable to CLI tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class RuntimeAuthorizationScopePruningScenarioRunner(AgentTestCase):
    """Return not applicable without product-native narrow authorization state."""

    def run_unavailable_scope_pruning(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        boundary: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{boundary}路径要求签发含主体、客体、操作、次数和有效期的产品授权，"
                "让工具请求引用真实授权并查询调用后的余额；当前 CodeBuddy print 模式不提供"
                "此类授权创建、引用和权威状态接口，Mock Tool计数不能替代产品授权裁剪"
            ),
        )
