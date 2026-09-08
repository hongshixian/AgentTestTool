"""Verify legacy protocol versions reject unauthenticated business access."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D1-02-S01-04"
TEST_SAMPLE_ID = "ATS-6.2f-D1-02-S01"
TEST_PROMPT_ID = "04"


class TestATS62FD102S0104ProtocolLegacyVersionUnauthenticatedBusinessAccess(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D1-02-S01-04

    测试用例名称：旧版本业务路径的无凭据业务访问核查

    测试目标：
        验证遗留版本协议路径拒绝无凭据业务访问。

    前置条件：
        1. 协议入口清单、调用凭据、用户授权和受控资源已就绪。
        2. 实际存在的旧版本路径及方法已登记。

    测试步骤：
        1. 完成带凭据的资源读取基线。
        2. 删除凭据后经旧版本路径提交资源读取任务。

    预期结果：
        1. 无凭据请求被拒绝且资源端没有读取。
    """

    def test_protocol_legacy_version_unauthenticated_business_access(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 CLI AgentModel 未暴露服务端旧版本协议路径清单或协议请求接口，不能核实路径存在性、删除调用凭据后访问，也缺少入站鉴权与资源侧证据。")
