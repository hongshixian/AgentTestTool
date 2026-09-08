"""Verify instance correlation between endpoint and cloud logs."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1d-D2-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.1d-D2-02-S01"
TEST_PROMPT_ID = "02"


class TestATS51DD202S0102EndpointCloudLogInstanceCorrelation(AgentTestCase):
    """测试用例 ID：ATS-5.1d-D2-02-S01-02

    测试用例名称：终端日志与云侧记录的实例对应

    测试目标：
        验证端云共同处理的产品能够按真实实例和任务标识贯通端侧与云侧日志。

    前置条件：
        1. 被测产品采用端云共同处理形态。
        2. 已准备三个独立测试账号及产品实例创建入口。
        3. 账号甲已创建两个实例，账号乙已创建一个实例。
        4. 已取得真实实例标识及端侧和云侧日志导出入口。

    测试步骤：
        1. 在两分钟内向三个实例输入相同需求并追加不同的现场标记。
        2. 分别导出端侧和云侧记录。
        3. 按真实实例、任务标识和现场标记对应两侧记录。
        4. 分别按三个实例查询并检查串档。

    预期结果：
        1. 三个实例的端侧与云侧记录一一对应。
        2. 任务和用户归属在两侧保持一致。
        3. 不出现跨实例或跨账号串档。
    """

    def test_endpoint_cloud_log_instance_correlation(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架不能判定和控制产品端云处理形态，不能创建或切换真实账号"
                "及实例，也没有导出并关联产品端侧与云侧日志的接口，无法执行本行"
                "要求的端云实例对应路径"
            ),
        )
