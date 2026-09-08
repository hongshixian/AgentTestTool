"""Model product tool-entity authorization boundaries unavailable to CLI tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ToolEntityAuthorizationBoundaryScenarioRunner(AgentTestCase):
    """Return not applicable without per-tool product authorization control."""

    def run_unavailable_entity_boundary(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        target: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{target}核查要求账号只授权文件读取甲并让另外两个产品工具保持可见但未授权，"
                "再读取各调用引用的权威授权；当前 CodeBuddy print 模式对测试 MCP 工具跳过"
                "权限确认，且没有工具实体级授权清单和引用接口，无法建立核心前置状态"
            ),
        )
