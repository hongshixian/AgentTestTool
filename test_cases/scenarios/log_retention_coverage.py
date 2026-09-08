"""Model cloud-log retention coverage paths unavailable to public CLI tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class LogRetentionCoverageScenarioRunner(AgentTestCase):
    """Return not applicable without authoritative product log-storage access."""

    def run_unavailable_retention_coverage(
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
                f"{storage_scope}核查要求产品权威资源枚举、生命周期配置、创建事件"
                "和清理作业记录；当前 CodeBuddy 公开 CLI 不开放云端日志后台，"
                "测试侧证据账本也不是产品日志存储，无法执行真实留存覆盖核查"
            ),
        )
