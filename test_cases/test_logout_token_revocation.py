"""Verify server-side revocation of an old token after explicit logout."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1c-D4-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.1c-D4-01-S01"
TEST_PROMPT_ID = "02"


class TestATS51CD401S0102LogoutTokenRevocation(AgentTestCase):
    """测试用例 ID：ATS-5.1c-D4-01-S01-02

    测试用例名称：主动注销后旧令牌失效

    测试目标：
        验证主动注销后保存的旧令牌在服务端失效，不能继续读取账号甲待办。

    前置条件：
        1. 已在账号甲写入三条未完成待办并确认正常可读。
        2. 已取得真实注销入口和安全日志入口。
        3. 可以安全保存并独立重放注销前服务端凭证。

    测试步骤：
        1. 正常读取待办并保存有效会话凭证副本。
        2. 通过真实注销入口提交注销并记录服务端成功响应。
        3. 不重新登录或刷新，使用旧凭证再次请求待办。
        4. 保存重放响应和安全日志。

    预期结果：
        1. 注销前凭证被服务端拒绝。
        2. 仅前端跳转或清除本地令牌而旧副本仍可用时不通过。
    """

    def test_logout_revokes_old_token_on_server(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 没有真实注销入口、原始服务端令牌导出或指定旧令牌重放接口，"
                "也不能预置和查询账号甲真实待办或安全日志；清理本地会话文件不能证明"
                "服务端令牌撤销，因此无法执行本行路径"
            ),
        )
