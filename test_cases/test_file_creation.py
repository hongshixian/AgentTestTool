"""Verify that the Agent creates a file with the requested content."""

import pytest

from agent_models import AgentModel, PermissionPolicy
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]
TEST_CASE_ID = "ATS-0.0x-D3-00-S01"


class TestATS00XD300S01FileCreation(AgentTestCase):
    """测试用例 ID：ATS-0.0x-D3-00-S01（本条用例是示例用例）

    测试用例名称：创建指定内容的文本文件（冒烟示例）

    测试目标：
        验证 Agent 能够在隔离工作目录中创建文件并写入指定内容。

    前置条件：
        1. Agent CLI 已安装并完成登录。
        2. Agent 可写入指定临时工作目录。
        3. 预设文件内容为“AgentTestTool file creation passed.”。

    测试步骤：
        1. 在临时工作目录启动 Agent 会话。
        2. 要求创建 agent_test_output.txt、写入预设文本并确认完成。

    预期结果：
        1. 文件创建交互正常完成。
        2. 临时工作目录中存在 agent_test_output.txt。
        3. 文件可按 UTF-8 读取，去除首尾空白后与预设文本一致。
    """

    def test_agent_creates_file_with_requested_content(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.assert_agent_authenticated(agent_model, request)
        if not agent_model.capabilities.file_operations:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason="被测 Agent 不具备文件操作能力",
            )
        file_name = "agent_test_output.txt"
        expected_content = "AgentTestTool file creation passed."
        prompt = (
            f"请在当前工作目录创建文件 {file_name}，文件内容必须恰好为："
            f"{expected_content} 完成后请简短确认。"
        )
        turn = agent_model.send_prompt(
            prompt,
            permission_policy=PermissionPolicy.ALLOW_WORKSPACE_EDITS,
        )
        self.assert_turn_completed(turn, request, agent_model)

        output_file = agent_model.workspace / file_name
        if not output_file.is_file():
            self.conclude_failed(
                request,
                agent_model,
                reason=f"Agent 未创建文件：{output_file}",
            )
        actual_content = output_file.read_text(encoding="utf-8").strip()
        if actual_content != expected_content:
            self.conclude_failed(
                request,
                agent_model,
                reason="Agent 创建的文件内容与预期不一致",
            )

        self.conclude_passed(
            request,
            agent_model,
            reason="Agent 已创建文件且完整内容与预期一致",
        )
