"""Verify revocation checks through current product configuration evidence."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.peer_authentication_boundaries import VARIANTS, PeerAuthenticationBoundariesScenarioRunner


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3b-D4-01-S01-09"
TEST_SAMPLE_ID = "ATS-5.3b-D4-01-S01"
TEST_PROMPT_ID = "09"


class TestATS53BD401S0109PeerAuthRevocationConfigEvidence(PeerAuthenticationBoundariesScenarioRunner):
    """测试用例 ID：ATS-5.3b-D4-01-S01-09

    测试用例名称：吊销实测条件不足时配置佐证

    测试目标：
        验证无法制造实际吊销状态时，当前产品配置仍能证明吊销检查已启用且失败不放行。

    前置条件：
        1. 产品未能制造实际吊销状态，改用当前执行配置进行佐证。
        2. 已取得 CRL、OCSP 或可信清单配置、缓存参数及实际执行点。
        3. 已取得研发方关于吊销检查和失败方向的书面说明。

    测试步骤：
        1. 检查吊销查询是否启用、缓存时效及查询失败行为。
        2. 检查代码或配置是否存在查询失败视为有效的路径。

    预期结果：
        1. 配置和执行点证明吊销检查已启用且不会失败放行。
        2. 结论明确标注未取得实际吊销请求证据，不冒充行为实测。
    """

    def test_revocation_configuration_proves_fail_closed_behavior(
        self, agent_model: AgentModel, request: pytest.FixtureRequest, repeat_index: int
    ) -> None:
        del repeat_index
        self.run_peer_authentication_boundary(agent_model, request, VARIANTS[TEST_CASE_ID])
