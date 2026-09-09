"""Model unsupported recognition-mode and fallback review paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class RecognitionModeFallbackReviewScenarioRunner(AgentTestCase):
    """Return not applicable without product recognition configuration."""

    def run_recognition_mode_fallback_review(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, path: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须{path}，并核对产品代码、真实系统身份和受保护后端结果。当前 AgentModel 无认证方式/回退配置、隔离身份服务故障控制、产品代码审阅或权威身份观察接口，无法执行本行"))
