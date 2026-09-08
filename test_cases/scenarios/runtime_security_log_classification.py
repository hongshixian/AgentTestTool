"""Model unsupported runtime and security log classification paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class RuntimeSecurityLogClassificationScenarioRunner(AgentTestCase):
    """Return not applicable without product log access."""

    def run_runtime_security_log_classification(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, scope: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须在{scope}触发普通操作和安全事件后，分别导出产品运行日志与安全日志并核对分类。当前 AgentModel 仅有评测方事件证据，不提供产品两类日志或实际安全判定的公开查询导出接口，无法执行本行"))
