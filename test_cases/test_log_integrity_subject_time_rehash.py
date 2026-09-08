"""Verify log integrity after subject and timestamp changes in an isolated copy."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_integrity_adversarial_boundaries import (
    VARIANTS,
    LogIntegrityBoundaryScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5c-D5-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.5c-D5-01-S01"
TEST_PROMPT_ID = "01"


class TestATS55CD501S0101LogIntegritySubjectTimeRehash(LogIntegrityBoundaryScenarioRunner):
    """测试用例 ID：ATS-5.5c-D5-01-S01-01

    测试用例名称：修改主体时间并重算哈希

    测试目标：
        验证隔离日志副本中的主体和时间改动即使重算单条哈希仍可被检出。

    前置条件：
        1. 已取得获授权的产品日志隔离演练副本。
        2. 已保存基线日志、哈希、链式凭据和独立锚点。
        3. 产品完整性核验及告警入口可用。

    测试步骤：
        1. 产生前后查询和中间拒绝事件并通过基线核验。
        2. 仅在隔离副本修改目标事件的主体和时间并重算单条哈希。
        3. 通过产品入口执行独立完整性核验。
        4. 保全证据后恢复隔离副本。

    预期结果：
        1. 链式约束或外部锚点检出主体和时间改动。
        2. 修改被阻止或核验结果可定位受影响记录或区间。
    """

    def test_log_integrity_subject_time_rehash(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_log_integrity_boundary(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
