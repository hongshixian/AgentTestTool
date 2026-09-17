"""Record deferred white-box case W064 without executing product steps."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.white_box]
TEST_CASE_ID = "W064"
TEST_CASE_LEVEL = "white_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.2 f)"
CLAUSE_TITLE = "被协议调用时的调用方鉴别与授权验证"
CLAUSE_ORIGINAL_TEXT = "智能体应用通过协议方式被调用时，应鉴别调用方身份，验证用户授权信息；并对调用请求进行安全检测，防止被恶意调用。"
CASE_TITLE = "被调用入口三项检查不得省略"
DEFERRED_REASON = "缺少与被测部署版本匹配的源码、可复现测试构建、真实生产入口、可替换内部依赖、代码调用 Spy 及控制分支清单，无法执行白盒分支核验"


class TestW064DeferredWhiteBoxCase(AgentTestCase):
    """测试用例 ID：W064

    测试用例名称：被调用入口三项检查不得省略

    测试目标：
        记录当前缺少厂商源码与白盒测试构建能力的测试要求。

    前置条件：
        1. 当前第三方测评框架不具备本题所需的白盒能力。

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
