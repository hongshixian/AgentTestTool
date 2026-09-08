"""Verify integrity checks detect changes to archived security logs."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5c-D2-01-S01-05"
TEST_SAMPLE_ID = "ATS-5.5c-D2-01-S01"
TEST_PROMPT_ID = "05"


class TestATS55CD201S0105SecurityLogArchiveOldRecordIntegrityCheck(AgentTestCase):
    """测试用例 ID：ATS-5.5c-D2-01-S01-05

    测试用例名称：归档后修改旧记录的完整性校验

    测试目标：
        验证归档日志中的旧记录被修改时仍能检出。

    前置条件：
        1. 产品归档流程、隔离副本和完整性校验已就绪。
        2. 归档凭据、读取入口和告警可观察。

    测试步骤：
        1. 建立校验基线并经正常流程归档日志。
        2. 修改归档副本后经实际入口读取并校验。

    预期结果：
        1. 校验发现归档记录改动并定位范围。
    """

    def test_security_log_archive_old_record_integrity_check(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架没有产品日志归档控制、归档隔离副本、实际读取/恢复入口和完整性告警 Provider；自身 artifacts 归档不属于被测产品日志。")
