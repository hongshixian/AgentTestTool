"""Verify that none plus a missing signature cannot bypass component verification."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S01-04"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S01"
TEST_PROMPT_ID = "04"


class TestATS54AD502S0104ComponentNoneAlgorithmMissingSignatureRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S01-04

    测试用例名称：算法 none 叠加删除签名时拒绝引入

    测试目标：
        验证 none 算法和缺失签名的组合不能打开免校验通道。

    前置条件：
        1. 已准备专用组件集成环境、合法签名制品及独立可信公钥。
        2. 已取得算法与签名字段位置、真实提交入口和测试凭据。
        3. 可查询校验、安全日志、集成部署记录及实际加载哈希。

    测试步骤：
        1. 提交合法制品并记录成功引入的基线哈希。
        2. 通过同一入口提交算法为 none 且删除签名字段的副本。
        3. 等待终态并查询校验、日志、部署和加载记录。

    预期结果：
        1. 合法制品成功引入，组合异常副本被校验入口拒绝。
        2. 两个异常叠加不形成免验通道，异常副本未被加载。
        3. 安全日志记录本次组合异常提交。
    """

    def test_component_none_algorithm_missing_signature_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有产品算法及签名字段结构、真实组件提交或验签入口，也"
                "不能查询集成部署、加载哈希和安全日志，无法执行组合异常验证"
            ),
        )
