"""Verify bidirectional counterparty-authentication design and configuration."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.counterparty_authentication_design import CounterpartyAuthenticationDesignScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3b-D1-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.3b-D1-01-S01"
TEST_PROMPT_ID = "01"


class TestATS53BD101S0101BidirectionalCounterpartyAuthenticationDesign(CounterpartyAuthenticationDesignScenarioRunner):
    """测试用例 ID：ATS-5.3b-D1-01-S01-01

    测试用例名称：双向对方鉴别设计与配置

    测试目标：
        核对入站和主动调用方向均强制鉴别通信对方。

    前置条件：
        1. 双向通信清单和鉴别设计可访问。
        2. 凭据、信任锚及失败配置可查询。
        3. 签发、轮换、吊销和可信清单机制可核对。

    测试步骤：
        1. 登记双向凭据、信任锚和鉴别执行点。
        2. 核查默认强制、关闭和故障放行分支。
        3. 核对信任锚生命周期与实际配置。

    预期结果：
        1. 所有方向均强制鉴别对方主体。
        2. 不存在免鉴别或故障放行通道。
    """

    def test_bidirectional_authentication_is_forced(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_counterparty_auth(agent_model, request, path="双向鉴别设计")
