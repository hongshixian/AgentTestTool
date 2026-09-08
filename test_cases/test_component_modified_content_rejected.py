"""Verify that modified component content with its old signature is rejected."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S03-04"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S03"
TEST_PROMPT_ID = "04"


class TestATS54AD502S0304ComponentModifiedContentRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S03-04

    测试用例名称：保留原签名篡改组件内容时拒绝引入

    测试目标：
        验证受签名保护的内容被改变后不能凭原签名通过校验。

    前置条件：
        1. 已准备专用组件集成环境、合法签名制品及独立可信公钥。
        2. 已确定受签名保护的业务内容和真实提交入口。
        3. 可查询验签、安全日志、部署记录及实际加载内容哈希。

    测试步骤：
        1. 提交合法制品并记录成功加载的基线哈希。
        2. 通过同一入口提交改变受保护内容但保留原签名的副本。
        3. 等待终态并查询验签、日志、部署和加载记录。

    预期结果：
        1. 合法制品成功引入，内容与签名不匹配的副本被拒绝。
        2. 异常副本未被集成、部署或先行加载。
        3. 安全日志关联本次提交及校验失败。
    """

    def test_component_modified_content_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有产品组件制品格式、签名覆盖范围和真实提交入口，也不能"
                "查询产品验签、部署终态、实际加载内容哈希或安全日志，无法执行该验证"
            ),
        )
