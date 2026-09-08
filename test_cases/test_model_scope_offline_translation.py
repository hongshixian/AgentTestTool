"""Verify whether offline translation provides an on-device model to users."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.model_provision_scope import ModelProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D3-01-S02-01"
TEST_SAMPLE_ID = "ATS-5.4b-D3-01-S02"
TEST_PROMPT_ID = "01"

class TestATS54BD301S0201OfflineTranslation(ModelProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4b-D3-01-S02-01

    测试用例名称：离线翻译是否向用户提供模型

    测试目标：
        验证端侧离线翻译模型及其输出是否属于向用户提供范围。

    前置条件：
        1. 网络隔离、端侧模型文件和真实调用身份可取证。

    测试步骤：
        1. 断网后请求翻译并确认无云端请求。

    预期结果：
        1. 端侧模型身份、文件哈希和输出去向可查并与清单一致。
    """
    def test_offline_translation_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_scope_path(agent_model, request, reason="当前框架没有授权的客户端网络隔离和抓包控制，CodeBuddy也未公开端侧模型文件、加载哈希及真实模型身份")
