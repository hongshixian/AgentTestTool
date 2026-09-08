"""Verify that a component with an oversized signature is rejected."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S03-06"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S03"
TEST_PROMPT_ID = "06"


class TestATS54AD502S0306ComponentOversizedSignatureRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S03-06

    测试用例名称：组件签名长度超出格式要求时拒绝引入

    测试目标：
        验证超过格式上限的签名不能经截取或跳过校验后被接受。

    前置条件：
        1. 已准备专用组件集成环境、合法签名制品及独立可信公钥。
        2. 已取得真实算法、签名长度上限、提交入口和测试凭据。
        3. 可查询校验、安全日志、集成部署记录及实际加载哈希。

    测试步骤：
        1. 提交合法制品并记录成功引入的基线哈希。
        2. 通过同一入口提交签名超过格式上限一个字节的副本。
        3. 等待终态并查询校验、日志、部署和加载记录。

    预期结果：
        1. 合法制品成功引入，超长签名副本被校验入口拒绝。
        2. 产品不截取签名后接受或跳过校验，异常副本未被加载。
        3. 安全日志关联提交及签名格式异常。
    """

    def test_component_oversized_signature_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有产品签名长度约束、真实组件提交和验签入口，也不能查询"
                "截取行为、集成部署、实际加载哈希或安全日志，无法执行超长签名验证"
            ),
        )
