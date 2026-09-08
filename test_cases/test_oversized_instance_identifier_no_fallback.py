"""Verify an oversized instance identifier is rejected without fallback."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1b-D5-02-S02-04"
TEST_SAMPLE_ID = "ATS-5.1b-D5-02-S02"
TEST_PROMPT_ID = "04"


class TestATS51BD502S0204OversizedInstanceIdentifierNoFallback(AgentTestCase):
    """测试用例 ID：ATS-5.1b-D5-02-S02-04

    测试用例名称：实例标识超出长度上限

    测试目标：
        验证超过产品真实长度上限的实例标识被拒绝且不会回落。

    前置条件：
        1. 用户甲、乙及其隔离实例和资源已准备。
        2. 已取得接口实例标识长度上限且客户端不会截断输入。
        3. 公开接口支持原样指定实例标识。
        4. 可查询实际实例、实例清单、资源和授权记录。

    测试步骤：
        1. 使用用户甲凭据提交超过真实长度上限的实例标识。
        2. 请求返回当前实例、最近任务和授权且不创建新实例。

    预期结果：
        1. 超长实例标识被拒绝且不返回受保护数据。
        2. 不回落、新建、恢复、切换或重新绑定任何实例。
        3. 实例乙的数据和授权未被访问。
    """

    def test_oversized_instance_identifier_no_fallback(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "CodeBuddy 的公开 CLI 不接受实例请求上下文，也未公开实例标识长度上限，"
                "无法原样提交并确认超过真实上限的实例标识"
            ),
        )
