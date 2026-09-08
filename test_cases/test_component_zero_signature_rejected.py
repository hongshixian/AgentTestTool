"""Verify that a component with an all-zero signature is rejected."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S03-02"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S03"
TEST_PROMPT_ID = "02"


class TestATS54AD502S0302ComponentZeroSignatureRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S03-02

    测试用例名称：组件签名为全零值时拒绝引入

    测试目标：
        验证等长全零签名不能因字段和长度合法而被接受。

    前置条件：
        1. 已准备专用组件集成环境、合法签名制品及可信公钥。
        2. 已取得真实签名长度、编码、提交入口和测试凭据。
        3. 可查询校验、安全日志、集成部署记录及实际加载哈希。

    测试步骤：
        1. 提交合法制品并记录成功引入的基线哈希。
        2. 通过同一入口提交仅将签名替换为等长全零值的副本。
        3. 等待终态并查询校验、日志、部署和加载记录。

    预期结果：
        1. 合法制品成功引入，全零签名副本未通过验签。
        2. 产品不只检查签名存在与长度，异常副本未被加载。
        3. 安全日志可关联本次校验失败。
    """

    def test_component_zero_signature_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有产品真实签名编码、组件提交和验签通道，也不能观察"
                "集成部署、实际加载哈希和安全日志，无法执行全零签名验证"
            ),
        )
