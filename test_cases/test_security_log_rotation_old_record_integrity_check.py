"""Verify integrity checks span log rotation and detect old-record changes."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5c-D2-01-S01-04"
TEST_SAMPLE_ID = "ATS-5.5c-D2-01-S01"
TEST_PROMPT_ID = "04"


class TestATS55CD201S0104SecurityLogRotationOldRecordIntegrityCheck(AgentTestCase):
    """测试用例 ID：ATS-5.5c-D2-01-S01-04

    测试用例名称：跨轮转修改旧记录的完整性校验

    测试目标：
        验证日志轮转后修改旧记录仍能被完整性校验发现。

    前置条件：
        1. 隔离日志副本、轮转入口和完整性校验已就绪。
        2. 跨文件凭据和告警可关联观察。

    测试步骤：
        1. 建立正常校验基线并使产品日志发生轮转。
        2. 修改旧日志副本后执行跨文件校验。

    预期结果：
        1. 校验发现旧记录改动且轮转边界无盲区。
    """

    def test_security_log_rotation_old_record_integrity_check(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前环境不能触发产品真实日志轮转、修改轮转旧文件副本或调用跨文件完整性校验；测试证据归档轮转不能替代产品日志机制。")
