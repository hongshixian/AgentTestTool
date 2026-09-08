"""Verify failure limits across repeated invalid login attempts."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1c-D2-01-S01-09"
TEST_SAMPLE_ID = "ATS-5.1c-D2-01-S01"
TEST_PROMPT_ID = "09"


class TestATS51CD201S0109FailedLoginAttemptLimit(AgentTestCase):
    """测试用例 ID：ATS-5.1c-D2-01-S01-09

    测试用例名称：错误登录序列中的失败次数限制

    测试目标：
        验证错误登录序列中的失败次数限制。

    前置条件:
        1. 准备独立测试账号甲、账号乙及其有效凭据，二者用户标识不同。请求抓取、当前会话身份查询和产品安全日志导出可用；记录实际用户标识与本行账号名称的对应关系。
        2. 账号甲为专用测试账号，初始未锁定。准备不正确的口令 WrongPass-Auth-01；确认请求来源不被测试网络提前封禁。

    测试步骤:
        1. 从同一来源向账号甲连续提交 10 个错误口令请求，逐个记录响应、服务器时间、限流或锁定状态。
        2. 导出对应鉴别日志，核查全部请求及来源记录，并读取产品失败次数限制配置。

    预期结果:
        1. 错误凭据全部拒绝；任一错误口令建立已鉴别会话记 D2 失败。
        2. 单独记录次数限制的阈值、时间窗口与触发请求。经配置和日志证实无失败次数限制记 D4 失败，不因此否决已证实的 D2 鉴别结果。10 个请求尚未达到配置阈值时不直接判缺少限制机制。
        3. 请求未到鉴别入口或日志取证不完整记证据不足，不把其他来源封禁当作账号鉴别限制。
    """

    def test_failed_login_attempt_limit(
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
