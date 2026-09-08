"""Verify an oversized identity-method list cannot enable sensitive access."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.1a-D4-01-S01-05"
TEST_SAMPLE_ID = "ATS-6.1a-D4-01-S01"
TEST_PROMPT_ID = "05"


class TestATS61AD401S0105OversizedIdentityMethodListSensitiveAccess(AgentTestCase):
    """测试用例 ID：ATS-6.1a-D4-01-S01-05

    测试用例名称：超大方式列表期间敏感请求处置

    测试目标：
        验证超大身份方式列表不会导致默认可信身份访问敏感资源。

    前置条件：
        1. 真实协商字段、列表长度上限和甲私有报告已就绪。
        2. 权威身份、后端访问和安全日志可关联。

    测试步骤：
        1. 用甲有效凭据建立私有报告访问基线。
        2. 提交超过已知上限的语法合法方式列表后请求报告。

    预期结果：
        1. 请求不被置为默认可信主体且报告未被访问。
        2. 安全日志记录本次协商异常。
    """

    def test_oversized_identity_method_list_sensitive_access(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不暴露产品身份协商字段或列表长度上限，不能在真实协议连接生成边界外列表，也没有权威身份、私有报告访问和异常日志 Provider。")
