"""Verify protected-resource access immediately before and after token expiry."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1c-D4-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.1c-D4-01-S01"
TEST_PROMPT_ID = "01"


class TestATS51CD401S0101TokenExpiryBoundary(AgentTestCase):
    """测试用例 ID：ATS-5.1c-D4-01-S01-01

    测试用例名称：令牌到期前后受保护任务访问

    测试目标：
        验证原凭据在到期前可访问账号甲待办，到期后被服务端拒绝且要求重新鉴别。

    前置条件：
        1. 已在账号甲写入三条未完成待办。
        2. 已取得真实凭据有效期、刷新策略和安全日志入口。
        3. 可以关闭评测客户端自动刷新并保留同一原凭据。

    测试步骤：
        1. 使用有效凭据建立会话并记录到期时间，关闭自动刷新。
        2. 到期前一分钟请求账号甲的三条待办。
        3. 到期后一分钟使用同一原凭据发出相同请求。
        4. 保存两次凭据引用、请求时间、响应和鉴别日志。

    预期结果：
        1. 到期前可读取账号甲的三条待办。
        2. 到期后原凭据被服务端拒绝并要求重新鉴别。
        3. 客户端自动换取新令牌的结果不能作为原令牌到期证据。
    """

    def test_original_token_is_rejected_after_expiry(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架不能读取或固定使用真实服务端令牌、取得精确到期时间、"
                "关闭 CodeBuddy 自动刷新或按同一旧令牌重放请求，也没有真实待办和鉴别日志"
                "查询接口，无法执行令牌到期边界测试"
            ),
        )
