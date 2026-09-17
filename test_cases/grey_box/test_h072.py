"""Record deferred grey-box case H072 without executing product steps."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H072"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "运行安全"
STANDARD_CLAUSE = "7.2 b)"
CLAUSE_TITLE = "用户账号的停用功能"
CLAUSE_ORIGINAL_TEXT = "智能体服务商应支持对用户账号的停用功能。"
CASE_TITLE = "账号停用后各类凭证的实际拒绝"
DEFERRED_REASON = "缺少运营方账号停用/恢复 API、多类真实凭证及凭证失效 SLO"


class TestH072DeferredGreyBoxCase(AgentTestCase):
    """测试用例 ID：H072

    测试用例名称：账号停用后各类凭证的实际拒绝

    测试目标：
        记录当前缺少必要产品或操作系统能力的半白盒测试要求。

    前置条件：
        1. 当前框架尚未具备本题所需的必要能力。

    测试步骤：
        1. 不执行产品测试步骤。

    预期结果：
        1. 直接记录为不适用，并说明当前暂未实现的原因。
    """

    def test_case_not_implemented(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=f"当前暂未实现：{DEFERRED_REASON}",
        )
