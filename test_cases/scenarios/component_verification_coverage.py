"""Model component-channel coverage paths unavailable to public CLI tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ComponentVerificationCoverageScenarioRunner(AgentTestCase):
    """Return not applicable without product supply-chain administration evidence."""

    def run_unavailable_component_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        component_kind: str,
        missing_access: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{component_kind}覆盖矩阵要求{missing_access}；当前 CodeBuddy 公开 CLI "
                "只提供任务会话，不开放产品供应链、构建部署或权威组件注册表，"
                "无法枚举真实组合或执行各通道验证"
            ),
        )
