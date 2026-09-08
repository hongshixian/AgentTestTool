"""Verify rejection of an invalid special-character login password."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1c-D2-01-S01-05"
TEST_SAMPLE_ID = "ATS-5.1c-D2-01-S01"
TEST_PROMPT_ID = "05"


class TestATS51CD201S0105LoginSpecialCharacterPasswordRejection(AgentTestCase):
    """测试用例 ID：ATS-5.1c-D2-01-S01-05

    测试用例名称：鉴别入口拒绝特殊字符口令

    测试目标：
        验证鉴别入口拒绝特殊字符口令。

    前置条件:
        1. 准备独立测试账号甲、账号乙及其有效凭据，二者用户标识不同。请求抓取、当前会话身份查询和产品安全日志导出可用；记录实际用户标识与本行账号名称的对应关系。
        2. 本行输入：用户名仍为账号甲，按接口正常编码提交四个特殊字符，确保请求格式合法且该值不是账号甲口令。

    测试步骤:
        1. 向真实登录入口提交账号甲与按单引号、双引号、反斜杠、分号顺序组成的四字符字符串，记录服务器响应及有无已鉴别会话。
        2. 保存原始请求、响应和时间，从安全日志核对本次鉴别事件的账号、成功或失败及请求来源。

    预期结果:
        1. 异常口令被拒绝，不建立已鉴别会话，不输出内部异常栈或明确账号存在性信息。
        2. 异常口令被接受记失败；采集本次失败鉴别及来源日志。
        3. 请求未到鉴别入口或采集失败时标记证据不足；证据明确证明鉴别绕过或应有日志缺失时记录对应失败。
    """

    def test_login_special_character_password_rejection(
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
