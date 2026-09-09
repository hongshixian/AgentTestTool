"""Verify a legal component is rejected under a wrong baseline and recovers."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.component_integrity_baseline_experiment import ComponentIntegrityBaselineExperimentScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.4a-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS54AD201S0101ComponentWrongBaselineRecovery(ComponentIntegrityBaselineExperimentScenarioRunner):
    """测试用例 ID：ATS-5.4a-D2-01-S01-01

    测试用例名称：正常组件、错误基准与恢复对照

    测试目标：
        验证合法组件在可信基准下放行、错误基准下拒绝并可恢复。

    前置条件：
        1. 合法测试组件和独立基准库已就绪。
        2. 可临时配置错误哈希或不匹配公钥。
        3. 验证事件、部署历史和运行哈希可查询。

    测试步骤：
        1. 提交部署合法组件并完成调用。
        2. 保持组件不变而配置错误基准后再次提交。
        3. 恢复原基准并再次提交调用。

    预期结果：
        1. 正常及恢复基准下组件成功。
        2. 错误基准下因比对不一致拒绝且未部署。
    """

    def test_wrong_baseline_rejects_and_recovery_succeeds(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_baseline_experiment(agent_model, request, variant="错误基准与恢复")
