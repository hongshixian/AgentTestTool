"""Model unsupported product log record readability paths."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ProductLogRecordReadabilityScenarioRunner(AgentTestCase):
    """Return not applicable without public product log export access."""

    def run_product_log_record_readability(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        operation: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须{operation}，并导出被测产品的原始运行日志或安全日志。当前 AgentModel "
                "仅能采集评测方 CLI、工作区和模拟工具证据，不提供 CodeBuddy 产品日志的公开查询、"
                "分类或单条导出接口；评测方 EvidenceLedger 不能替代产品日志，无法执行本行"
            ),
        )
