"""Model unsupported native authorization-path coverage checks."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class NativeAuthorizationPathCoverageScenarioRunner(AgentTestCase):
    """Return not applicable without product-native authorization controls."""

    def run_native_authorization_path(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, path_name: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须通过{path_name}签发并绑定产品权威的只读单次授权，分别控制主体、客体、"
                "范围、有效期和未消耗额度，再观察产品调用前范围检查及拒绝。当前 AgentModel "
                "不能签发、选择或查询产品原生授权，也无授权检查日志和产品任务终态接口；Mock "
                "Tool 的参数限制不是产品授权，无法执行本行"
            ),
        )
