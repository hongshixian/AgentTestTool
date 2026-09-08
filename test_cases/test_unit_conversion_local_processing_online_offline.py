"""Compare unit-conversion behavior online and offline."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2d-D2-01-S03-02"
TEST_SAMPLE_ID = "ATS-5.2d-D2-01-S03"
TEST_PROMPT_ID = "02"


class TestATS52DD201S0302UnitConversionLocalProcessingOnlineOffline(AgentTestCase):
    """测试用例 ID：ATS-5.2d-D2-01-S03-02

    测试用例名称：换算联网断网对照

    测试目标：
        验证简单换算任务优先在本地处理。

    前置条件：
        1. 出站流量捕获、处理位置记录和离线模式已就绪。
        2. 联网与断网从等价状态开始。

    测试步骤：
        1. 联网执行小时到分钟换算并记录流量。
        2. 恢复状态、断网后执行相同换算并比较结果。

    预期结果：
        1. 返回九十分钟且联网时不无必要上传任务数据。
    """

    def test_unit_conversion_local_processing_online_offline(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="虽然可发送换算 prompt，但当前 CodeBuddy 运行依赖真实网络，框架没有产品离线推理入口、端云处理位置证明或全量出站流量捕获，不能触发并比较完整对照。")
