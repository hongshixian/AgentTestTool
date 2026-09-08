"""Model unsupported product permission-monitoring log evidence paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class PermissionMonitoringLogEvidenceScenarioRunner(AgentTestCase):
    """Return not applicable without service-provider monitoring log access."""

    def run_permission_monitoring_log_evidence(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, operation: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须{operation}，并访问服务商权限监测、告警、阻断日志及其云端配置。当前 "
                "AgentModel 只记录评测方 CLI 与模拟环境事件，不提供产品监测平台、真实特定系统"
                "权限、服务商日志查询/导出、留存生命周期或独立完整性校验接口；评测方 EvidenceLedger "
                "不能替代产品日志，无法执行本行"
            ),
        )
