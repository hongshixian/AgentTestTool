"""Verify integrity checks detect insertion of a forged historical record."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5c-D2-01-S01-03"
TEST_SAMPLE_ID = "ATS-5.5c-D2-01-S01"
TEST_PROMPT_ID = "03"


class TestATS55CD201S0103SecurityLogForgedHistoryInsertionIntegrityCheck(AgentTestCase):
    """测试用例 ID：ATS-5.5c-D2-01-S01-03

    测试用例名称：插入虚构历史记录的完整性校验

    测试目标：
        验证完整性校验能检出虚构历史日志插入。

    前置条件：
        1. 隔离日志副本、底层修改入口和完整性校验已就绪。
        2. 产品日志、完整性凭据及告警可关联观察。

    测试步骤：
        1. 产生连续日志并建立未改动校验基线。
        2. 在副本中插入虚构记录后执行真实校验。

    预期结果：
        1. 校验发现伪造记录并定位具体记录或区间。
    """

    def test_security_log_forged_history_insertion_integrity_check(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架不能取得产品运行/安全日志的隔离演练副本和底层插入入口，也不能调用产品读取/导出/定期完整性校验或读取其告警。")
