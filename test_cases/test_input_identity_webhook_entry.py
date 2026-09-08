"""Verify input identification coverage for webhook events."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.input_identity_entry_coverage import (
    VARIANTS,
    InputIdentityEntryScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.1a-D1-02-S01-05"
TEST_SAMPLE_ID = "ATS-6.1a-D1-02-S01"
TEST_PROMPT_ID = "05"


class TestATS61AD102S0105InputIdentityWebhookEntry(InputIdentityEntryScenarioRunner):
    """测试用例 ID：ATS-6.1a-D1-02-S01-05

    测试用例名称：Webhook纳入识别及方式交集

    测试目标：
        核查 Webhook 事件入口已纳入输入方识别且采用双方共同支持方式。

    前置条件：
        1. 已准备用户甲和用户乙的独立账号、注册身份资料及权威身份查询。
        2. 已取得客户端与服务端支持的识别方式、协议字段和凭据绑定位置。
        3. 评测事件服务主体丙及真实 Webhook 订阅入口已注册。

    测试步骤：
        1. 通过路由、注册、订阅和部署配置确认本行入口真实存在。
        2. 服务主体丙使用产品实际认证字段向 Webhook 发送会议事件。
        3. 核对识别策略、双方支持方式交集和接入记录，并交叉验证不存在声明。

    预期结果：
        1. Webhook 发送方被有效识别，接入记录与真实服务主体一致。
        2. 入口不以内网或固定服务身份免识别，清单外入口也不存在识别遗漏。
        3. 本行只验证覆盖和识别方式配置，不宣称对抗有效。
    """

    def test_input_identity_webhook_entry(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_input_identity_entry_coverage(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
