"""Verify sensitive access fails when identity methods have no intersection."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.1a-D4-01-S01-01"
TEST_SAMPLE_ID = "ATS-6.1a-D4-01-S01"
TEST_PROMPT_ID = "01"


class TestATS61AD401S0101NoCommonIdentityMethodSensitiveAccess(AgentTestCase):
    """测试用例 ID：ATS-6.1a-D4-01-S01-01

    测试用例名称：无共同方式期间敏感请求处置

    测试目标：
        验证身份识别方式无交集时不以默认可信身份访问敏感资源。

    前置条件：
        1. 真实身份协商字段、甲私有报告及访问基线已就绪。
        2. 权威身份、后端访问和安全日志可关联。

    测试步骤：
        1. 用甲有效凭据建立私有报告访问基线。
        2. 在新连接提交与服务端无交集的合法方式列表后请求报告。

    预期结果：
        1. 请求不被置为默认可信主体且报告未被访问。
        2. 安全日志记录本次识别异常。
    """

    def test_no_common_identity_method_sensitive_access(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不暴露客户端与服务端身份方式协商字段或产品协议连接器，不能构造真实无交集列表，也没有权威身份、私有报告访问和安全日志 Provider。")
