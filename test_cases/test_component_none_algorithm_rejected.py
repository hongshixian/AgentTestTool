"""Verify that a component declaring the none algorithm is rejected."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S01"
TEST_PROMPT_ID = "01"


class TestATS54AD502S0101ComponentNoneAlgorithmRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S01-01

    测试用例名称：组件签名算法改为 none 时拒绝引入

    测试目标：
        验证组件将签名算法声明为 none 时不能绕过完整性校验。

    前置条件：
        1. 已准备专用组件集成环境、合法签名制品及独立可信公钥。
        2. 已取得真实提交入口、算法字段位置和所需测试凭据。
        3. 可查询校验、安全日志、集成部署记录及实际加载哈希。

    测试步骤：
        1. 提交合法制品并记录成功加载的基线哈希。
        2. 通过同一入口提交仅将算法声明改为 none 的副本。
        3. 等待终态并查询校验、日志、部署和加载记录。

    预期结果：
        1. 合法制品成功引入，none 算法副本在校验入口被拒绝。
        2. 异常副本未被集成、部署或加载。
        3. 安全日志记录异常提交及拒绝原因。
    """

    def test_component_none_algorithm_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 没有产品组件制品提交、签名校验或集成部署入口，"
                "也不能查询实际加载哈希与安全日志，无法执行 none 算法降级验证"
            ),
        )
