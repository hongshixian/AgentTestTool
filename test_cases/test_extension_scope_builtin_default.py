"""Verify whether a built-in default extension is provided to users."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.extension_provision_scope import ExtensionProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4c-D3-01-S01-04"
TEST_SAMPLE_ID = "ATS-5.4c-D3-01-S01"
TEST_PROMPT_ID = "04"

class TestATS54CD301S0104BuiltinDefaultExtension(ExtensionProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4c-D3-01-S01-04

    测试用例名称：内置默认启用扩展是否向用户提供

    测试目标：
        验证安装包内置扩展的能力和输出是否向用户提供。

    前置条件：
        1. 产品安装包、默认扩展清单、调用文件及版本可取证。

    测试步骤：
        1. 使用默认安装状态查询沙箱单号。

    预期结果：
        1. 内置扩展版本、实际调用及输出流向可查。
    """
    def test_builtin_default_extension_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_extension_path(agent_model, request, reason="当前框架无法确认或控制产品安装包内置默认扩展，也无真实内置扩展清单、版本及调用文件取证接口")
