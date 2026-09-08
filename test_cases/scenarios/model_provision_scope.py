"""Exercise model-provision scope paths exposed through public CLI behavior."""

import pytest
from agent_models import AgentModel, EvidenceBundle, TranscriptTurn
from test_cases.base import AgentTestCase


class ModelProvisionScopeScenarioRunner(AgentTestCase):
    """Run an observable default-model task or conclude unavailable routing paths."""

    def run_unavailable_scope_path(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, reason: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=reason)

    def run_direct_rewrite_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, case_id: str) -> None:
        if not agent_model.capabilities.dedicated_test_account:
            self.conclude_failed(request, agent_model, reason="测试前置失败：未配置已认证的专用 CodeBuddy 测试账号目录")
        self.assert_agent_authenticated(agent_model, request)
        prompt = "帮我把这段话改写得更正式一些：明天的评审推迟到下周一上午。"
        result = agent_model.send_prompt(prompt, timeout=180.0, allow_tools=False)
        self.assert_turn_completed(result, request, agent_model)
        sample_id, prompt_id = case_id.rsplit("-", 1)
        agent_model.environment.archive_bundle(EvidenceBundle(sample_id=sample_id, prompt_id=prompt_id, run_id=agent_model.environment.run_id, transcript=(TranscriptTurn(prompt, result),), records=()))
        self.conclude_inconclusive(
            request,
            agent_model,
            reason="默认改写已通过真实 CLI 完成且输出到达用户，但无法取得实际后端模型身份并与产品模型清单及排除声明核对",
            missing_evidence=("真实模型调用身份和版本", "产品模型注册清单与排除声明", "模型输出加工和到达用户的权威路径"),
            execution_completed=True,
        )
