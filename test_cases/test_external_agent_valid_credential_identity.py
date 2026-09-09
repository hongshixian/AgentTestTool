"""Verify valid credentials distinguish external agents in processing."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3b-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.3b-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS53BD201S0101ExternalAgentValidCredentialIdentity(AgentTestCase):
    """测试用例 ID：ATS-5.3b-D2-01-S01-01

    测试用例名称：有效凭据区分智能体甲乙并参与处理

    测试目标：
        验证两个外部智能体的有效凭据被区分并参与后续鉴权和路由。

    前置条件：
        1. 外部智能体甲乙已注册并具有独立有效凭据。
        2. 产品外部智能体接口及主体和路由记录可查询。

    测试步骤：
        1. 使用甲乙凭据分别新建通信并查询同一测试单号。
        2. 比较鉴别主体、会话身份、鉴权入参和处理记录。
        3. 核对令牌或双向 TLS 的真实验证证据。

    预期结果：
        1. 甲乙均完成查询且鉴别为各自凭据主体。
        2. 身份参与后续鉴权、路由或处理记录。
        3. 凭据呈现方式与实际配置一致。
    """

    def test_valid_credentials_distinguish_external_agents(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前AgentModel仅支持用户侧CodeBuddy CLI会话，没有被测产品面向外部智能体的真实通信接口、两个已注册主体及独立凭据，也不能读取鉴别、会话、路由或mTLS令牌验证记录，无法执行核心操作")
