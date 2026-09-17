"""Verify that the Agent edits an existing file to the requested content."""

from __future__ import annotations

import pytest

from agent_models import AgentModel, PermissionPolicy
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]
TEST_CASE_ID = "ATS-0.0x-D4-00-S01"


class TestATS00XD400S01FileEditing(AgentTestCase):
    """测试用例 ID：ATS-0.0x-D4-00-S01（本条用例是示例用例）

    测试用例名称：编辑已有文本文件（冒烟示例）

    测试目标：
        验证 Agent 能够在隔离工作目录中编辑已有文件并准确替换文件内容。

    前置条件：
        1. Agent CLI 已安装并完成登录。
        2. Agent 可读写指定临时工作目录。
        3. 临时工作目录中已预置待编辑文本文件。

    测试步骤：
        1. 在临时工作目录预置 agent_test_edit_target.txt。
        2. 启动 Agent 会话并要求其将文件内容替换为指定文本。

    预期结果：
        1. 文件编辑交互正常完成。
        2. 预置文件仍然存在并可按 UTF-8 读取。
        3. 文件完整内容与指定文本完全一致。
    """

    def test_agent_edits_existing_file_with_requested_content(
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

        file_name = "agent_test_edit_target.txt"
        initial_content = "AgentTestTool file editing pending."
        expected_content = "AgentTestTool file editing passed."
        target_file = agent_model.workspace / file_name

        try:
            target_file.write_text(initial_content, encoding="utf-8")
        except OSError as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"测试前置文件创建失败：{type(error).__name__}",
            )

        prompt = (
            f"请编辑当前工作目录中已经存在的文件 {file_name}，"
            "将文件全部内容替换为下面目标文本；不要添加空格、换行、Markdown 标记或其他内容，"
            "也不要创建新文件。\n"
            f"目标文本：{expected_content}\n"
            "完成后请简短确认。"
        )
        try:
            turn = agent_model.send_prompt(
                prompt,
                permission_policy=PermissionPolicy.ALLOW_WORKSPACE_EDITS,
            )
        except Exception as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"Agent 文件编辑交互失败：{type(error).__name__}",
            )
        self.assert_turn_completed(turn, request, agent_model)

        if not target_file.is_file():
            self.conclude_failed(
                request,
                agent_model,
                reason=f"Agent 编辑后目标文件不存在：{target_file}",
            )
        try:
            actual_content = target_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            self.conclude_failed(
                request,
                agent_model,
                reason=f"Agent 编辑后的文件无法按 UTF-8 读取：{type(error).__name__}",
            )
        if actual_content != expected_content:
            self.conclude_failed(
                request,
                agent_model,
                reason="Agent 编辑后的文件完整内容与预期不一致",
            )

        self.conclude_passed(
            request,
            agent_model,
            reason="Agent 已将预置文件的完整内容准确替换为指定文本",
        )
