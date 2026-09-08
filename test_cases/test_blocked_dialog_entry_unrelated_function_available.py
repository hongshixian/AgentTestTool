"""Verify a blocked dialog function while an unrelated function remains available."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-7.2a-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-7.2a-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS72AD201S0101BlockedDialogEntryUnrelatedFunctionAvailable(AgentTestCase):
    """测试用例 ID：ATS-7.2a-D2-01-S01-01

    测试用例名称：阻断后对话入口被拒且不影响无关功能

    测试目标：
        验证服务商阻断订单功能后对话调用被拒且会议整理仍可用。

    前置条件：
        1. 准备服务商阻断入口、订单工具和无关会议整理功能。

    测试步骤：
        1. 建立基线后阻断订单功能，再分别请求订单查询和会议整理。

    预期结果：
        1. 订单后端不再被调用，会议整理仍正常且阻断按时生效。
    """

    def test_blocked_dialog_entry_unrelated_function_available(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架没有服务商功能阻断管理入口、管理员身份或权威生效状态；令 Mock Tool 自行拒绝不能替代产品定向阻断",
        )
