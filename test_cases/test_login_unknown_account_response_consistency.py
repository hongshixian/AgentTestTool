"""Verify consistent login rejection for wrong and unknown accounts."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1c-D2-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.1c-D2-01-S01"
TEST_PROMPT_ID = "02"


class TestATS51CD201S0102LoginUnknownAccountResponseConsistency(AgentTestCase):
    """测试用例 ID：ATS-5.1c-D2-01-S01-02

    测试用例名称：错误口令拒绝且不暴露账号是否存在

    测试目标：
        验证错误口令拒绝且不暴露账号是否存在。

    前置条件:
        1. 准备独立测试账号甲、账号乙及其有效凭据，二者用户标识不同。请求抓取、当前会话身份查询和产品安全日志导出可用；记录实际用户标识与本行账号名称的对应关系。
        2. 准备一个经管理员确认不存在的测试用户名，使用与账号甲相同长度的名称；错误口令固定为 WrongPass-Auth-01，且不等于任一有效口令。

    测试步骤:
        1. 分别向登录入口提交‘账号甲+错误口令’和‘不存在用户名+相同错误口令’，保持其余请求字段一致。
        2. 比对两次响应中的错误码、提示文字及是否建立会话；不通过单次时延差异推断账号枚举。
        3. 保存原始请求、响应和时间，从安全日志核对本次鉴别事件的账号、成功或失败及请求来源。

    预期结果:
        1. 两次鉴别均拒绝，不获得已鉴别会话。错误码和提示不直接区分账号存在与否。
        2. 任一请求登录成功，或明确提示一个账号存在而另一个不存在，记失败。
        3. 请求未到鉴别入口或采集失败时标记证据不足；证据明确证明鉴别绕过或应有日志缺失时记录对应失败。
    """

    def test_login_unknown_account_response_consistency(
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
