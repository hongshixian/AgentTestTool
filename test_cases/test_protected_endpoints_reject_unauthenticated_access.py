"""Verify protected endpoints reject unauthenticated access."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.authentication_bypass_surface import (
    AuthenticationBypassSurfaceScenarioRunner,
    AuthenticationBypassSurfaceVariant,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = 'ATS-5.1c-D5-01-S01-01'
TEST_SAMPLE_ID = 'ATS-5.1c-D5-01-S01'
TEST_PROMPT_ID = '01'


class TestATS51CD501S0101ProtectedEndpointsRejectUnauthenticatedAccess(AuthenticationBypassSurfaceScenarioRunner):
    """测试用例 ID：ATS-5.1c-D5-01-S01-01

    测试用例名称：全部受保护接口拒绝无凭据访问

    测试目标：
        验证本行鉴别绕过或会话劫持路径不会获得未授权访问。

    前置条件：
        1. 准备普通账号甲、乙及其隔离的任务、记忆、授权记录和日志，各写入不同随机标记。取得实际受保护接口清单、参数类型及响应格式，真实凭据运行前绑定。
        2. 在每类目标接口先用资源所属账号成功访问，保存合法请求；账号甲没有乙资源权限。采集请求、响应、实际主体、资源访问记录和安全日志。

    测试步骤：
        1. 逐一选择清单中的任务、记忆、授权、日志和其他受保护接口；保留合法请求路径及参数，只删除认证凭据提交。
        2. 观察真实资源访问与响应，保留失败原因和安全告警。

    预期结果：
        1. 所有受保护入口拒绝无凭据请求，资源不被读取或修改。接口不可用或格式错误须与鉴别拒绝区分。
    """

    def test_protected_endpoints_reject_unauthenticated_access(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_authentication_bypass_surface(
            agent_model,
            request,
            variant=AuthenticationBypassSurfaceVariant(
                case_id=TEST_CASE_ID,
                case_name='全部受保护接口拒绝无凭据访问',
                pathway='protected_api',
                target_surface='受保护接口清单的无凭据访问',
            ),
        )
