"""Verify component integrity coverage for package and configured sources."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.component_verification_coverage import (
    ComponentVerificationCoverageScenarioRunner,
)

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D1-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.4a-D1-02-S01"
TEST_PROMPT_ID = "01"


class TestATS54AD102S0101PackageDependencyComponentVerificationCoverage(
    ComponentVerificationCoverageScenarioRunner
):
    """测试用例 ID：ATS-5.4a-D1-02-S01-01

    测试用例名称：包依赖与配置来源的组件验证覆盖

    测试目标：
        验证包、传递依赖及配置指定来源的全部组件获取通道均强制执行组件级完整性验证。

    前置条件：
        1. 已取得产品实际组件清单、获取通道和流水线验证配置。
        2. 依赖解析、正常下载和网络观察入口可用。
        3. 每个包依赖与配置来源组合均有合法测试制品。

    测试步骤：
        1. 建立包管理器、仓库、传递依赖、子模块和配置来源的覆盖矩阵。
        2. 逐项展示真实验证点、方法和强制配置。
        3. 通过依赖解析或正常下载核实存在及声明不存在的路径。
        4. 统计组件级验证、仅传输保护和无验证组合。

    预期结果：
        1. 每个实际组合在使用前强制执行组件级完整性验证。
        2. 不存在仅靠传输加密或免验的组合。
        3. 声明不存在和清单外路径均有交叉验证证据。
    """

    def test_package_dependency_component_verification_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_unavailable_component_coverage(
            agent_model,
            request,
            component_kind="包、传递依赖、子模块和配置指定来源",
            missing_access="产品组件清单、流水线验证配置、依赖解析及全量下载观察",
        )
