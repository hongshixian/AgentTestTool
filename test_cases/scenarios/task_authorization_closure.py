"""Model same-task native authorization closure paths unavailable to print-mode CLI."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class TaskAuthorizationClosureScenarioRunner(AgentTestCase):
    """Return not applicable without product-native authorization lifecycle controls."""

    def run_unavailable_authorization_closure(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        operation: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{operation}闭环必须保持初次操作未授权、在产品原生界面授权、同任务复用"
                "授权并在对象变化后再次保持未授权；当前 CodeBuddy print 模式固定跳过工具"
                "权限确认，不能批准、拒绝、变更或查询绑定任务与参数的授权，无法执行"
            ),
        )
