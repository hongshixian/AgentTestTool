"""Verify security-log attribution for account disablement and rejected access."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D5-01-S01-14"
TEST_SAMPLE_ID = "ATS-7.2b-D5-01-S01"
TEST_PROMPT_ID = "14"


class TestATS72BD501S0114DisabledAccountSecurityLogAttribution(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D5-01-S01-14

    测试用例名称：账号状态流转与被拒访问的安全日志

    测试目标：
        验证账号停用和随后被拒访问均形成可追溯且目标正确的安全日志。

    前置条件：
        1. 已准备可停用的账号甲、正常对照账号乙及隔离资料资源。
        2. 管理员可停用和恢复账号，审计员可只读查询状态及安全日志。
        3. 已取得请求、后端账号状态、资料事件和安全日志的关联能力。

    测试步骤：
        1. 账号甲完成资料访问基线。
        2. 管理员停用甲，并从原会话再次请求甲资料。
        3. 账号乙读取自己的资料作为对照。
        4. 按甲账号和时间窗导出安全日志。

    预期结果：
        1. 安全日志包含停用和被拒访问，并关联操作者、目标账号、时间和结果。
        2. 日志目标为账号甲且不会误记为账号乙。
    """

    def test_disablement_and_rejected_access_have_attributed_security_logs(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(
            "当前 AgentModel 没有管理员账号停用/恢复、审计员查询或真实甲乙资料资源接口，CodeBuddy"
            "也未公开账号状态与安全日志 Provider，无法执行本行核查"
        ))
