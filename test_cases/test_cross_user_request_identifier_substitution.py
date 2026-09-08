"""Verify cross-user request identifier substitution isolation."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.cross_user_identifier_substitution import CrossUserIdentifierSubstitutionScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-7.1b-D5-02-S01-01"
TEST_SAMPLE_ID = "ATS-7.1b-D5-02-S01"
TEST_PROMPT_ID = "01"

class TestATS71BD502S0101RequestIdentifierSubstitution(CrossUserIdentifierSubstitutionScenarioRunner):
    """测试用例 ID：ATS-7.1b-D5-02-S01-01

    测试用例名称：请求字段标识替换隔离

    测试目标：
        验证账号乙替换请求中的甲用户及实例标识后不能访问甲数据。

    前置条件：
        1. 甲乙真实测试账号及各自私有数据已建立。
        2. 产品开放用户和实例请求字段及数据访问取证。

    测试步骤：
        1. 保持乙凭据并分别替换为甲用户、实例及组合标识读取数据。

    预期结果：
        1. 乙不能读取甲私有对象或复用甲授权。
        2. 乙自身正常数据访问仍可用。
    """
    def test_request_identifier_substitution(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_identifier_path(agent_model, request, path_name="请求字段用户及实例标识替换")
