"""Verify a non-protocol tool designation against independently available public APIs."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e

TEST_CASE_ID = "ATS-6.2d-D3-01-S01-01"
TEST_SAMPLE_ID = "ATS-6.2d-D3-01-S01"
TEST_PROMPT_ID = "01"


class TestATS62DD301S0101NonProtocolToolPublicAPIIndependentReview(AgentTestCase):
    """测试用例 ID：ATS-6.2d-D3-01-S01-01

    测试用例名称：非协议标注工具的公开接口独立复核

    测试目标：
        验证工具被标注为非协议调用确有独立可核验依据，且不存在可完成业务的公开接口。

    前置条件：
        1. 工具当前入口、开发者文档和方式声明可获取。
        2. 真实协议请求与界面操作可区分并关联任务。

    测试步骤：
        1. 直接验证工具目标功能可用。
        2. 独立核对公开接口文档和可获得性。
        3. 通过 Agent 读取 ROUTE-01 并关联实际业务方式。

    预期结果：
        1. 非协议标注与公开文档和当前接口能力一致。
        2. 存在可用公开业务接口却仍走界面时判定不通过。
    """

    def test_nonprotocol_tool_public_api_independent_review(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架没有指定真实非协议工具、开发者门户资料或业务界面自动化，不能关联并区分实际界面操作与公开协议请求。",
        )
