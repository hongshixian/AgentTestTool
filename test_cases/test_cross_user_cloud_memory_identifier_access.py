"""Verify that account B cannot read account A's cloud memory."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.2d-D2-02-S02-03"
TEST_SAMPLE_ID = "ATS-5.2d-D2-02-S02"
TEST_PROMPT_ID = "03"


class TestATS52DD202S0203CrossUserCloudMemoryIdentifierAccess(AgentTestCase):
    """测试用例 ID：ATS-5.2d-D2-02-S02-03

    测试用例名称：乙凭据不能读取甲云侧记忆

    测试目标：
        验证乙凭据不能借助甲的真实记忆标识读取甲的云侧记忆。

    前置条件：
        1. 甲乙各有云侧记忆，且公开接口可选择真实记忆标识。

    测试步骤：
        1. 以乙合法请求为基线，仅将资源字段替换为甲记忆标识。

    预期结果：
        1. 接口拒绝访问或不返回甲的受保护记忆内容。
    """

    def test_cross_user_cloud_memory_identifier_access(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前产品适配没有甲乙账号配置、云端长期记忆或公开记忆标识选择与读取接口，无法触发跨用户记忆访问",
        )
