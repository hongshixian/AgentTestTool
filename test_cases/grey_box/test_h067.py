"""Record deferred grey-box case H067 without executing product steps."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H067"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.3 b)"
CLAUSE_TITLE = "特定系统权限的告知与用户同意"
CLAUSE_ORIGINAL_TEXT = "智能体应用使用特定系统权限前，应向用户告知具体的系统权限、用途及安全风险，并获取用户同意。"
CASE_TITLE = "拒绝系统权限后无调用与绕道"
DEFERRED_REASON = "缺少 OS 定位权限授予、拒绝、复位及 wifi scan 绕道观测能力"


class TestH067DeferredGreyBoxCase(AgentTestCase):
    """测试用例 ID：H067

    测试用例名称：拒绝系统权限后无调用与绕道

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
