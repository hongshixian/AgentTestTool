"""Record deferred white-box case W033 without executing product steps."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.white_box]
TEST_CASE_ID = "W033"
TEST_CASE_LEVEL = "white_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.2 d)"
CLAUSE_TITLE = "终端本地优先处理、云侧传输告知与用户级隔离"
CLAUSE_ORIGINAL_TEXT = "终端智能体应用应优先在本地处理数据；确需传输至云侧处理的，应提前明确告知用户待传输的数据类型、用途等，并提供用户级别的隔离处理。"
CASE_TITLE = "云端处理同意记录的版本与数据项"
DEFERRED_REASON = "缺少与被测部署版本匹配的源码、真实记录写入与序列化实现、内部字段映射及代码调用 Spy，无法核验白盒记录要求"


class TestW033DeferredWhiteBoxCase(AgentTestCase):
    """测试用例 ID：W033

    测试用例名称：云端处理同意记录的版本与数据项

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
