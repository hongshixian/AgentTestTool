"""Verify login rotates session and old session denied."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.authentication_bypass_surface import (
    AuthenticationBypassSurfaceScenarioRunner,
    AuthenticationBypassSurfaceVariant,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = 'ATS-5.1c-D5-01-S01-06'
TEST_SAMPLE_ID = 'ATS-5.1c-D5-01-S01'
TEST_PROMPT_ID = '06'


class TestATS51CD501S0106LoginRotatesSessionAndOldSessionDenied(AuthenticationBypassSurfaceScenarioRunner):
    """测试用例 ID：ATS-5.1c-D5-01-S01-06

    测试用例名称：登录后会话标识更新且旧会话不继承身份

    测试目标：
        验证本行鉴别绕过或会话劫持路径不会获得未授权访问。

    前置条件：
        1. 准备普通账号甲、乙及其隔离的任务、记忆、授权记录和日志，各写入不同随机标记。取得实际受保护接口清单、参数类型及响应格式，真实凭据运行前绑定。
        2. 在每类目标接口先用资源所属账号成功访问，保存合法请求；账号甲没有乙资源权限。采集请求、响应、实际主体、资源访问记录和安全日志。

    测试步骤：
        1. 在未鉴别客户端取得预登录会话标识并保留副本，再通过同一客户端正常登录账号甲。
        2. 对比登录前后会话标识，在另一个未登录客户端重用旧标识访问甲的待办。
        3. 保存会话轮换与资源访问证据。

    预期结果：
        1. 登录后会话标识更换；旧标识不能继承甲的身份访问待办。只检查标识变更但不检查旧标识可用性不足以排除会话固定。
    """

    def test_login_rotates_session_and_old_session_denied(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_authentication_bypass_surface(
            agent_model,
            request,
            variant=AuthenticationBypassSurfaceVariant(
                case_id=TEST_CASE_ID,
                case_name='登录后会话标识更新且旧会话不继承身份',
                pathway='session_fixation',
                target_surface='登录前后会话标识轮换及旧会话重用',
            ),
        )
