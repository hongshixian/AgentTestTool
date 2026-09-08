"""Verify server rejection when a request uses another account's instance identifier."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1b-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.1b-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS51BD201S0101ServerRejectsForeignInstanceTampering(AgentTestCase):
    """测试用例 ID：ATS-5.1b-D2-01-S01-01

    测试用例名称：服务端拒绝他人实例篡改

    测试目标：
        验证服务端拒绝账号甲凭据搭配账号乙真实实例标识的篡改请求。

    前置条件：
        1. 已准备账号甲、乙及其真实实例、身份和凭据。
        2. 实例乙已具有甲无权读取的私有便签和便签工具授权。
        3. 已取得实际身份、便签、授权和安全日志的查询入口。
        4. 请求包含可编辑实例标识且已准备报文修改转发能力。

    测试步骤：
        1. 在实例甲提交待办任务并保存成功请求。
        2. 将同类新请求的实例标识替换为实例乙标识后提交。
        3. 提交未篡改的新请求验证正常路径仍成功。
        4. 查询实际执行主体、任务变化和实例校验日志。

    预期结果：
        1. 服务端拒绝篡改请求且不采用实例乙身份。
        2. 请求不读取实例乙数据、不复用授权且不改变实例状态。
        3. 拒绝由实例标识校验触发而非普通重放防护。
        4. 实际身份与资源记录不足时不得推断通过。
    """

    def test_server_rejects_foreign_instance_tampering(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架不能创建和切换真实账号实例，不能捕获、修改或重放产品"
                "服务端请求中的实例标识，也没有查询实际执行身份、真实资源、授权"
                "和实例校验日志的接口，无法执行本行他人实例篡改路径"
            ),
        )
