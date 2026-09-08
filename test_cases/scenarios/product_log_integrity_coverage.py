"""Model unsupported product log integrity coverage paths."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ProductLogIntegrityCoverageScenarioRunner(AgentTestCase):
    """Return not applicable without product storage administration access."""

    def run_product_log_integrity_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        storage_scope: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须枚举并核查被测产品的{storage_scope}、生命周期记录和信任域隔离。当前 "
                "AgentModel 没有服务商日志存储控制台、资源清单、保护策略、密钥锚点、删除/轮转记录"
                "或存储账号权限的公开接口；本地工作区和证据账本不能替代产品存储，无法执行本行"
            ),
        )
