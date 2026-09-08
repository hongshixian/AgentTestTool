"""Model low-risk batch authorization paths unavailable to print-mode CLI tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class BatchAuthorizationModificationScenarioRunner(AgentTestCase):
    """Return not applicable without product batch-authorization management."""

    def run_unavailable_batch_authorization(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        operation_set: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{operation_set}闭环必须用产品授权管理界面或公开 API 创建带有效期的"
                "整体授权单元、移出单项并整体取消；当前 CodeBuddy 无授权管理入口，"
                "且 print 模式固定跳过工具权限，不能取得或修改授权单元，无法执行"
            ),
        )
