"""Model actual product storage-location checks unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ActualStorageLocationScenarioRunner(AgentTestCase):
    """Return not applicable without backend storage searches."""

    def run_unavailable_storage_search(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, scope: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{scope}要求在产品主从库、索引、日志、备份、分析和训练存储中检索标记并绑定实际资源地域；第三方CLI只能提交文本，不能查询这些服务端载体，故无法完成核心落盘验证"))
