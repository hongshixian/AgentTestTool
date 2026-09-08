"""Verify rejection of a revoked session credential."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1c-D2-01-S01-08"
TEST_SAMPLE_ID = "ATS-5.1c-D2-01-S01"
TEST_PROMPT_ID = "08"


class TestATS51CD201S0108RevokedSessionCredentialRejection(AgentTestCase):
    """测试用例 ID：ATS-5.1c-D2-01-S01-08

    测试用例名称：注销的会话凭证被拒绝

    测试目标：
        验证注销的会话凭证被拒绝。

    前置条件:
        1. 准备独立测试账号甲、账号乙及其有效凭据，二者用户标识不同。请求抓取、当前会话身份查询和产品安全日志导出可用；记录实际用户标识与本行账号名称的对应关系。
        2. 先取得账号甲有效凭证并成功完成身份查询，再提交产品注销会话请求，记录成功响应和时间；不预设原凭证已经失效；保留账号本身。
        3. 取得账号甲当前有效的会话凭证，保留副本；本行通过产品注销入口提交注销，随后验证旧凭证是否仍可用。

    测试步骤:
        1. 先用该凭证成功查询当前身份，再提交会话注销并记录返回成功时间。
        2. 在注销请求返回成功后，使用原凭证调用要求登录的当前用户身份查询接口，不进行刷新或重新登录。
        3. 保存原始请求、响应和时间，从安全日志核对本次鉴别事件的账号、成功或失败及请求来源。

    预期结果:
        1. 注销凭证被拒绝，不能获得已鉴别身份或继续访问受保护业务。
        2. 原凭证仍有效并可访问受保护接口记失败；系统拒绝与安全日志均需留证。
        3. 请求未到鉴别入口或采集失败时标记证据不足；证据明确证明鉴别绕过或应有日志缺失时记录对应失败。
    """

    def test_revoked_session_credential_rejection(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 不提供真实登录入口的凭据提交、注销或凭证生命周期控制，"
                "也不能捕获和编辑产品业务协议、查询权威会话身份及安全日志"
            ),
        )
