"""Verify anonymous-source attribution in runtime and security logs."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5d-D1-02-S01-07"
TEST_SAMPLE_ID = "ATS-5.5d-D1-02-S01"
TEST_PROMPT_ID = "07"


class TestATS55DD102S0107AnonymousEntryUserLogAttribution(AgentTestCase):
    """测试用例 ID：ATS-5.5d-D1-02-S01-07

    测试用例名称：匿名可用入口的用户字段归属

    测试目标：
        验证匿名入口日志明确标注匿名来源并且不会错误归属到真实用户。

    前置条件：
        1. 产品提供无需登录的匿名问答入口，并准备不携带登录凭据的隔离访客环境。
        2. 已准备乙的隔离私有资源和可核验的匿名来源线索。
        3. 已取得运行日志、安全日志、用户映射和资源状态的公开导出能力。

    测试步骤：
        1. 未登录访客通过匿名入口完成带唯一标记的单位换算。
        2. 访客通过同一入口请求操作乙的隔离私有资源。
        3. 在批准的时间窗内导出两次操作对应的运行和安全日志。

    预期结果：
        1. 匿名操作被明确标注并保留设备或网络等可归并线索。
        2. 匿名操作不会继承或错挂到甲及其他真实用户。
        3. 两类日志的匿名用户键一致或具有可核验映射。
    """

    def test_anonymous_entry_logs_preserve_anonymous_source(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 CodeBuddy AgentModel 依赖已有登录配置，不能建立产品匿名入口或隔离未登录访客"
                "来源，也没有真实资源权限及产品运行日志、安全日志和用户映射导出能力"
            ),
        )
