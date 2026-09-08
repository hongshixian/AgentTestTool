"""Verify instance identifier non-reuse across accounts and reauthentication."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1a-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.1a-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS51AD201S0101CrossAccountInstanceIdentifierReuse(AgentTestCase):
    """测试用例 ID：ATS-5.1a-D2-01-S01-01

    测试用例名称：跨账号创建及重新登录后的实例标识不复用

    测试目标：
        验证跨账号及重新登录后创建的实例使用不同完整标识，且历史记录保持可查。

    前置条件：
        1. 已准备账号甲、乙、丙和统一天气配置。
        2. 产品支持创建具有独立生命周期的 Agent 实例。
        3. 管理界面可以导出完整实例标识、所属账号、创建时间和历史记录。

    测试步骤：
        1. 账号甲创建两个实例，账号乙、丙各创建一个实例，并输入相同天气指令。
        2. 导出四个实例的完整标识、所属账号和创建时间。
        3. 账号甲退出并重新登录，再创建实例并输入相同天气指令。
        4. 导出五个实例记录，逐对比较标识并按旧标识查询历史归属。

    预期结果：
        1. 五个完整实例标识互不相同且不复用历史标识。
        2. 历史标识仍能查询到对应实例和账号。
        3. 标识不是连续自增、纯时间戳或可预测分配。
        4. 只展示会话编号或缺少标识、时间和历史证据时不能完成验证。
    """

    def test_cross_account_and_reauthentication_do_not_reuse_instance_ids(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 不能创建、切换或重新登录三个真实账号，也没有产品实例"
                "创建、完整权威标识导出和历史归属查询接口；CLI 会话 ID 不能代替实例标识，"
                "因此无法执行跨账号实例创建和标识复用核查"
            ),
        )
