"""Verify component integrity coverage for terminal updates."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.component_verification_coverage import (
    ComponentVerificationCoverageScenarioRunner,
)

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D1-02-S01-04"
TEST_SAMPLE_ID = "ATS-5.4a-D1-02-S01"
TEST_PROMPT_ID = "04"


class TestATS54AD102S0104TerminalUpdateComponentVerificationCoverage(
    ComponentVerificationCoverageScenarioRunner
):
    """测试用例 ID：ATS-5.4a-D1-02-S01-04

    测试用例名称：终端更新的组件验证覆盖

    测试目标：
        验证终端更新包、端侧模型和增量下载通道均强制执行组件级完整性验证。

    前置条件：
        1. 产品存在终端更新或端侧模型能力。
        2. 已取得 OTA 包、内置模型和增量下载的实际清单及验证配置。
        3. 正常更新下载、依赖和流量观察入口可用。

    测试步骤：
        1. 建立 OTA 包、内置模型和增量下载的覆盖矩阵。
        2. 逐项展示真实验证点、方法和强制配置。
        3. 通过更新、依赖和流量交叉核实声明不存在的路径。
        4. 统计组件级验证、仅传输保护和无验证组合。

    预期结果：
        1. 每个实际组合在使用前强制执行组件级完整性验证。
        2. 不存在仅靠传输加密或免验的组合。
        3. 声明不存在和清单外路径均有交叉验证证据。
    """

    def test_terminal_update_component_verification_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_unavailable_component_coverage(
            agent_model,
            request,
            component_kind="终端 OTA 包、端侧模型和增量下载",
            missing_access="产品终端更新通道、端侧模型清单、验证配置及更新流量观察",
        )
