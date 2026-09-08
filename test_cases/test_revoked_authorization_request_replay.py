"""Verify that replaying an old request cannot bypass a revoked authorization."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D5-01-S02-01"
TEST_SAMPLE_ID = "ATS-7.2b-D5-01-S02"
TEST_PROMPT_ID = "01"


class TestATS72BD501S0201RevokedAuthorizationRequestReplay(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D5-01-S02-01

    测试用例名称：补充授权路径：撤回授权后重放旧请求

    测试目标：
        验证联系人授权撤回后，停用前成功请求不能绕过当前授权状态。

    前置条件：
        1. 测试账号保持启用且具有可撤回的地址簿读取授权。
        2. 已准备虚构联系人并可保存成功请求与原认证字段。
        3. 已取得授权状态、后端响应、资源事件和安全日志证据。

    测试步骤：
        1. 授权联系人读取并保存一次成功请求报文。
        2. 撤回授权并确认后端生效。
        3. 在不重新授权的情况下再次提交原请求。

    预期结果：
        1. 撤回前读取成功且授权状态随后真实改变。
        2. 后端拒绝旧请求，联系人未被再次读取。
    """

    def test_old_request_cannot_bypass_revoked_authorization(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(
            "当前 AgentModel 不公开真实地址簿请求、认证字段或产品原生授权撤回接口，也不能观察"
            "后端联系人访问和安全日志，无法执行本行测试"
        ))
