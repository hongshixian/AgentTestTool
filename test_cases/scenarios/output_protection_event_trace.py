"""Model unsupported output-protection event trace paths."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class OutputProtectionEventTraceScenarioRunner(AgentTestCase):
    """Return not applicable without public product security-log access."""

    def run_output_protection_event_trace(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        action: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须触发{action}后导出被测产品安全日志，并按现场标记和真实会话标识双向检索。"
                "当前 AgentModel 可发 Prompt 和记录评测方事件，但无产品安全日志导出、输出防护事件查询"
                "或稳定会话标识反查接口；EvidenceLedger 不能替代产品日志，无法执行本行"
            ),
        )
