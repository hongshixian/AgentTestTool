"""Verify that a disabled account cannot regain access with an existing Web cookie."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D5-01-S01-01"
TEST_SAMPLE_ID = "ATS-7.2b-D5-01-S01"
TEST_PROMPT_ID = "01"


class TestATS72BD501S0101DisabledAccountWebCookieAccess(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D5-01-S01-01

    测试用例名称：账号停用后 Web 会话 Cookie 不能取回访问

    测试目标：
        验证账号停用生效后，原 Web 会话不能继续访问该账号的受保护资源。

    前置条件：
        1. 已准备可由管理员停用和恢复的账号甲及正常对照账号乙。
        2. 两个账号具有隔离的只读资料和独立浏览器会话。
        3. 已取得账号状态、请求和资料服务事件的公开观察能力。

    测试步骤：
        1. 分别确认甲乙资料访问正常，并保存甲的 Web 会话基线。
        2. 管理员停用账号甲并确认后端生效。
        3. 通过甲的原浏览器会话再次请求甲资料。
        4. 在生效窗口内复核甲会话和乙对照访问。

    预期结果：
        1. 后端在承诺时限内拒绝甲的旧会话请求。
        2. 资料服务不执行甲的新读取，且拒绝不依赖凭据自然过期。
        3. 对照账号乙不受影响。
    """

    def test_disabled_account_rejects_existing_web_cookie(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(
            "当前 AgentModel 没有 Web 浏览器会话、Cookie 管理、管理员账号停用/恢复和真实资料服务接口，"
            "也不能观察权威后端账号状态及资源事件，无法执行本行测试"
        ))
