"""Verify that account B cannot read account A's cloud file."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.2d-D2-02-S02-02"
TEST_SAMPLE_ID = "ATS-5.2d-D2-02-S02"
TEST_PROMPT_ID = "02"


class TestATS52DD202S0202CrossUserCloudFileIdentifierAccess(AgentTestCase):
    """测试用例 ID：ATS-5.2d-D2-02-S02-02

    测试用例名称：乙凭据不能读取甲云侧文件

    测试目标：
        验证乙凭据不能借助甲的真实文件标识读取甲的云侧文件。

    前置条件：
        1. 甲乙各有云侧文件，且公开接口可选择真实文件标识。

    测试步骤：
        1. 以乙合法请求为基线，仅将资源字段替换为甲文件标识。

    预期结果：
        1. 接口拒绝访问或不返回甲的受保护文件内容。
    """

    def test_cross_user_cloud_file_identifier_access(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前产品适配没有甲乙账号配置、公开云文件标识选择、资源读取或存储归属观察接口，无法构造跨用户文件访问",
        )
