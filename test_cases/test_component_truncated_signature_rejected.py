"""Verify that a component with a truncated signature is rejected."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S03-05"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S03"
TEST_PROMPT_ID = "05"


class TestATS54AD502S0305ComponentTruncatedSignatureRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S03-05

    测试用例名称：组件签名被截断时拒绝引入

    测试目标：
        验证缺少末尾字节的签名不能被忽略或转入免验证路径。

    前置条件：
        1. 已准备专用组件集成环境、合法签名制品及独立可信公钥。
        2. 已取得实际签名字节长度、编码、提交入口和测试凭据。
        3. 可查询校验、安全日志、集成部署记录及实际加载哈希。

    测试步骤：
        1. 提交合法制品并记录成功引入的基线哈希。
        2. 通过同一入口提交签名末尾少一个字节的副本。
        3. 等待终态并查询校验、日志、部署和加载记录。

    预期结果：
        1. 合法制品成功引入，截断签名副本被校验入口拒绝。
        2. 产品不忽略缺失字节或切换免验路径，异常副本未被加载。
        3. 安全日志记录签名异常及提交标识。
    """

    def test_component_truncated_signature_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有产品真实签名长度、编码和组件提交入口，也不能查询验签、"
                "部署终态、实际加载哈希或安全日志，无法执行截断签名验证"
            ),
        )
