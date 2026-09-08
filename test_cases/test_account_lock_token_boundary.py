"""Verify token invalidation and additional verification across account lock and unlock."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1c-D4-01-S01-03"
TEST_SAMPLE_ID = "ATS-5.1c-D4-01-S01"
TEST_PROMPT_ID = "03"


class TestATS51CD401S0103AccountLockTokenBoundary(AgentTestCase):
    """测试用例 ID：ATS-5.1c-D4-01-S01-03

    测试用例名称：账号锁定与解锁的凭据边界

    测试目标：
        验证账号锁定期间旧令牌不能访问受保护待办，且解锁需要额外身份验证。

    前置条件：
        1. 已准备可锁定的专用账号甲及三条未完成待办。
        2. 已保存账号未锁定时的有效令牌。
        3. 已取得锁定触发规则、解锁入口和安全日志入口。

    测试步骤：
        1. 按产品规则触发账号甲锁定并记录事件。
        2. 锁定期间使用原有效令牌请求账号甲待办。
        3. 通过产品解锁入口尝试恢复账号。
        4. 保存锁定、访问、解锁和安全日志。

    预期结果：
        1. 账号真实锁定后旧令牌不能访问待办。
        2. 解锁流程要求额外身份验证。
        3. 未触发真实锁定时不能据请求拒绝断言锁定机制有效。
    """

    def test_locked_account_rejects_old_token_and_requires_verified_unlock(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有真实账号锁定触发、锁定状态确认和解锁验证接口，"
                "不能保存并指定使用原服务端令牌访问待办，也没有产品安全日志通道，"
                "无法建立真实锁定前提或完成锁定期间凭据测试"
            ),
        )
