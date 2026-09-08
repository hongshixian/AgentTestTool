"""Verify that a component with an empty signature is rejected."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S03-01"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S03"
TEST_PROMPT_ID = "01"


class TestATS54AD502S0301ComponentEmptySignatureRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S03-01

    测试用例名称：组件签名为空字符串时拒绝引入

    测试目标：
        验证签名字段存在但值为空时不能绕过完整性验证。

    前置条件：
        1. 已准备专用组件集成环境、合法签名制品及独立可信公钥。
        2. 已取得签名字段编码、真实提交入口和所需测试凭据。
        3. 可查询校验、安全日志、集成部署记录及实际加载哈希。

    测试步骤：
        1. 提交合法制品并记录成功引入的基线哈希。
        2. 通过同一入口提交仅将签名值设为空字符串的副本。
        3. 等待终态并查询校验、日志、部署和加载记录。

    预期结果：
        1. 合法制品成功引入，空签名副本被校验入口拒绝。
        2. 字段存在但无值不绕过验证，异常副本未被加载。
        3. 安全日志记录空签名及本次提交。
    """

    def test_component_empty_signature_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有产品签名字段结构、真实组件提交和验签入口，也不能查询"
                "集成部署、实际加载哈希或安全日志，无法执行空签名验证"
            ),
        )
