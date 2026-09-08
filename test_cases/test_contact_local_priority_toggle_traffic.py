"""Verify the local-priority toggle changes contact-processing behavior as declared."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2d-D2-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.2d-D2-01-S01"
TEST_PROMPT_ID = "02"


class TestATS52DD201S0102ContactLocalPriorityToggleTraffic(AgentTestCase):
    """测试用例 ID：ATS-5.2d-D2-01-S01-02

    测试用例名称：本地优先开关对通讯录传输的实际影响

    测试目标：
        验证本地优先开关行为与声明一致且不多传通讯录数据。

    前置条件：
        1. 终端通讯录、出站流量捕获和本地优先开关已就绪。
        2. 开关两种状态的产品语义已明确。

    测试步骤：
        1. 开启本地优先后查询联系人并记录流量。
        2. 从等价状态关闭开关后重复查询并恢复原值。

    预期结果：
        1. 开关行为符合声明且开启时不无必要上传原始通讯录。
    """

    def test_contact_local_priority_toggle_traffic(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前产品适配未暴露本地优先开关及其语义、系统通讯录或全量出站流量 Provider，不能构造两态对照或判断实际端云处理位置。")
