"""Verify container and internal ports reject unauthenticated business access."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D1-02-S01-05"
TEST_SAMPLE_ID = "ATS-6.2f-D1-02-S01"
TEST_PROMPT_ID = "05"


class TestATS62FD102S0105ProtocolInternalPortUnauthenticatedBusinessAccess(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D1-02-S01-05

    测试用例名称：容器或内网监听端口的无凭据业务访问核查

    测试目标：
        验证容器或内网端口拒绝无凭据业务访问。

    前置条件：
        1. 协议入口清单、调用凭据、用户授权和受控资源已就绪。
        2. 内外部测试位置和真实路由端口已登记。

    测试步骤：
        1. 完成带凭据的资源读取基线。
        2. 从登记位置无凭据访问容器或内网业务端口。

    预期结果：
        1. 可达业务入口拒绝请求且资源端没有读取。
    """

    def test_protocol_internal_port_unauthenticated_business_access(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前测试环境没有被测产品容器/内网真实路由与端口清单、内部测试位置或协议调用连接器；本地 HTTP 接收端只属于测试工具，不能替代产品入口。")
