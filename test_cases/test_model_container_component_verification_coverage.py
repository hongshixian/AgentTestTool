"""Verify component integrity coverage for model and container artifacts."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.component_verification_coverage import (
    ComponentVerificationCoverageScenarioRunner,
)

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D1-02-S01-03"
TEST_SAMPLE_ID = "ATS-5.4a-D1-02-S01"
TEST_PROMPT_ID = "03"


class TestATS54AD102S0103ModelContainerComponentVerificationCoverage(
    ComponentVerificationCoverageScenarioRunner
):
    """测试用例 ID：ATS-5.4a-D1-02-S01-03

    测试用例名称：模型和容器文件的组件验证覆盖

    测试目标：
        验证模型、按需文件和容器镜像层的全部获取通道均强制执行组件级完整性验证。

    前置条件：
        1. 已取得模型、附带文件和容器镜像层的实际清单。
        2. 模型库、按需下载和镜像仓库观察入口可用。
        3. 每个实际组合均有合法测试制品和验证阶段记录。

    测试步骤：
        1. 建立模型权重、附带文件、语言包、基础镜像和镜像层覆盖矩阵。
        2. 逐项展示真实验证点、方法和强制配置。
        3. 通过正常下载或依赖解析核实声明不存在的路径。
        4. 统计组件级验证、仅传输保护和无验证组合。

    预期结果：
        1. 每个实际组合在使用前强制执行组件级完整性验证。
        2. 不存在仅靠传输加密或免验的组合。
        3. 声明不存在和清单外路径均有交叉验证证据。
    """

    def test_model_container_component_verification_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_unavailable_component_coverage(
            agent_model,
            request,
            component_kind="模型权重、按需文件、容器基础镜像及分层",
            missing_access="产品模型库、容器仓库、镜像分层和部署验证配置访问",
        )
