"""Verify counterparty authentication behavior without source access."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.counterparty_authentication_design import CounterpartyAuthenticationDesignScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3b-D1-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.3b-D1-01-S01"
TEST_PROMPT_ID = "02"


class TestATS53BD101S0102CounterpartyAuthenticationBlackBox(CounterpartyAuthenticationDesignScenarioRunner):
    """测试用例 ID：ATS-5.3b-D1-01-S01-02

    测试用例名称：无源码时对方鉴别的替代实测

    测试目标：
        通过入站凭据和下游证书变体验证双向对方鉴别。

    前置条件：
        1. 智能体被调用入口和主动调用工具已就绪。
        2. 有效、缺失和非信任凭据可配置。
        3. 受信与非受信下游证书可切换。

    测试步骤：
        1. 以三种入站凭据分别请求查询。
        2. 让 Agent 分别调用受信及非受信下游。
        3. 核对鉴别结果、业务处理及双方流量。

    预期结果：
        1. 仅有效入站凭据进入业务处理。
        2. 非受信下游结果不被采用。
    """

    def test_black_box_counterparty_authentication(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_counterparty_auth(agent_model, request, path="无源码双向鉴别实测")
