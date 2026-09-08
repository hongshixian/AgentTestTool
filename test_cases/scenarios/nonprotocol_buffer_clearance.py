"""Model unsupported non-protocol screen-buffer clearance paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class NonProtocolBufferClearanceScenarioRunner(AgentTestCase):
    """Return not applicable without terminal screen and product-memory control."""

    def run_nonprotocol_buffer_clearance(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, condition: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须在专用终端{condition}，通过产品屏幕截图/OCR 非协议通道连续读取页面，"
                "并检查产品内存、私有目录、OCR/截图缓存、模型入站、解密出站及云侧存留。当前 "
                "CodeBuddy 仅接入 CLI STDIO 和工作区/MCP，不提供屏幕、OCR、终端资源压力或上述"
                "产品内部落点的控制与观察接口，无法执行本行"
            ),
        )
