"""Verify that a well-formed but invalid component signature is rejected."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S03-03"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S03"
TEST_PROMPT_ID = "03"


class TestATS54AD502S0303ComponentRandomInvalidSignatureRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S03-03

    测试用例名称：组件签名格式合法但内容无效时拒绝引入

    测试目标：
        验证格式与长度合法但不匹配制品的签名仍被真实验签拒绝。

    前置条件：
        1. 已准备专用组件集成环境、合法签名制品及独立可信公钥。
        2. 已取得实际签名格式并可独立确认测试签名无效。
        3. 可查询产品验签、安全日志、部署记录及实际加载哈希。

    测试步骤：
        1. 提交合法制品并记录成功引入的基线哈希。
        2. 通过同一入口提交仅替换为格式合法无效签名的副本。
        3. 等待终态并查询验签、日志、部署和加载记录。

    预期结果：
        1. 合法制品成功引入，无效签名副本被真实验签拒绝。
        2. 产品不只检查字段、长度或编码，异常副本未被加载。
        3. 安全日志记录校验失败及提交标识。
    """

    def test_component_random_invalid_signature_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有可信公钥、独立签名验证、产品组件提交或真实验签入口，"
                "也不能查询部署、加载哈希和安全日志，无法执行格式合法无效签名验证"
            ),
        )
