"""Verify instance identifier non-reuse and history after terminal-app reinstallation."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1a-D2-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.1a-D2-01-S01"
TEST_PROMPT_ID = "02"


class TestATS51AD201S0102ReinstallInstanceIdentifierReuse(AgentTestCase):
    """测试用例 ID：ATS-5.1a-D2-01-S01-02

    测试用例名称：终端应用重装后新实例标识不复用、旧记录可查

    测试目标：
        验证终端应用重装后创建的新实例不复用完整标识，且重装前历史记录保持可查。

    前置条件：
        1. 已准备账号甲、乙、丙和统一天气配置。
        2. 产品支持创建实例并导出完整标识、账号、创建时间和历史记录。
        3. 已准备可恢复的专用测试设备并备份数据。
        4. 可以卸载和重装同一版本终端应用。

    测试步骤：
        1. 三个账号创建四个实例并输入相同天气指令。
        2. 账号甲重新登录后创建第五个实例并执行相同指令。
        3. 卸载并重装同版本应用，使用账号甲创建新实例并执行相同指令。
        4. 比较全部标识并查询重装前实例的账号和历史记录。

    预期结果：
        1. 全部完整实例标识互不相同且不复用历史标识。
        2. 重装前标识仍能查询到对应实例和账号。
        3. 标识不是连续自增、纯时间戳或可预测分配。
        4. 只展示会话编号或缺少标识、时间和历史证据时不能完成验证。
    """

    def test_reinstall_does_not_reuse_instance_ids_or_break_history(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有专用终端设备备份、应用卸载和同版本重装控制能力，"
                "也不能管理三个真实账号及产品实例或查询完整权威实例历史；"
                "因此无法执行重装前后标识复用和历史连续性核查"
            ),
        )
