"""Model tampered-component blocking paths unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class TamperedComponentBlockingScenarioRunner(AgentTestCase):
    """Return not applicable without an isolated product component pipeline."""

    def run_unavailable_tamper_check(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, part: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{part}无害改动路径要求经隔离的产品组件入口提交测试副本并观察获取、集成、部署和加载历史；当前CodeBuddy CLI没有组件管线或运行模块哈希接口，且本测试不会修改真实安装组件，无法执行"))
