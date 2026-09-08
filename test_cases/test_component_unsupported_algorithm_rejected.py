"""Verify that a component using an unsupported signature algorithm is rejected."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S01-03"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S01"
TEST_PROMPT_ID = "03"


class TestATS54AD502S0103ComponentUnsupportedAlgorithmRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S01-03

    测试用例名称：组件指定不支持的签名算法时拒绝引入

    测试目标：
        验证未知签名算法不会被解释为免验证或静默回退。

    前置条件：
        1. 已准备专用组件集成环境、合法签名制品及独立可信公钥。
        2. 已取得产品支持算法清单、真实提交入口和所需测试凭据。
        3. 可查询校验、安全日志、集成部署记录及实际加载哈希。

    测试步骤：
        1. 提交合法制品并记录成功引入的基线哈希。
        2. 通过同一入口提交仅声明已确认不受支持算法的副本。
        3. 等待终态并查询校验、日志、部署和加载记录。

    预期结果：
        1. 合法制品成功引入，未知算法副本被校验入口拒绝。
        2. 产品不回退到免验证状态，异常副本未被加载。
        3. 安全日志可关联算法错误及本次提交。
    """

    def test_component_unsupported_algorithm_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有产品支持算法清单、真实组件提交和验签入口，也无法观察"
                "静默回退、集成部署、实际加载及安全日志，无法执行未知算法验证"
            ),
        )
