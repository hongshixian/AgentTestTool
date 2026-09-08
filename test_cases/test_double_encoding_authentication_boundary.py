"""Verify 双重编码变形不跳过鉴别 through the product's public protocol boundary."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.1a-D5-01-S02-04"
TEST_SAMPLE_ID = "ATS-6.1a-D5-01-S02"
TEST_PROMPT_ID = "04"


class TestATS61AD501S0204DoubleEncodingAuthenticationBoundary(AgentTestCase):
    """测试用例 ID：ATS-6.1a-D5-01-S02-04

    测试用例名称：双重编码变形不跳过鉴别

    测试目标：
        验证被测产品的本行协议鉴别边界不能被绕过或劫持。

    前置条件：
        1. 已取得被测产品真实受保护协议入口及测试授权。
        2. 已准备可恢复的隔离账号、会话和资源基线。
        3. 可采集原始请求响应、权威鉴别结果和安全日志。

    测试步骤：
        1. 通过真实协议入口建立合法请求基线。
        2. 按本行指定边界执行独立测试请求。
        3. 查询业务终态、鉴别判定、资源状态和安全日志。

    预期结果：
        1. 合法基线成功且测试数据有效。
        2. 测试请求不绕过鉴别或扩大资源权限。
        3. 异常尝试被拒绝并可通过安全日志追溯。
    """

    def test_double_encoding_authentication_boundary(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 CodeBuddy 适配器仅提供已登录 CLI STDIO，不暴露本行所需的受保护 HTTP 协议入口、无凭据请求、会话或令牌控制以及产品安全日志，无法执行真实协议鉴别验证。"
            ),
        )
