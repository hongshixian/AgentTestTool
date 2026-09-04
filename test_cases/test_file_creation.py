"""Verify that the Agent creates a file with the requested content."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.base import AgentTestCase


pytestmark = pytest.mark.e2e


class TestATS00XD300S01FileCreation(AgentTestCase):
    """测试用例 ID：ATS-0.0x-D3-00-S01（本条用例是示例用例）

    测试用例名称：Agent 创建指定内容的文件

    测试目标：
        验证 Agent 能够在隔离工作目录中创建文件并写入指定内容。

    前置条件：
        1. 被测 Agent CLI 已安装。
        2. 被测 Agent 已完成登录认证。
        3. 被测 Agent 具有工作目录文件写入能力。
        4. Judge 模型 API 配置可用。

    测试步骤：
        1. 初始化使用临时工作目录的被测 Agent Model。
        2. 检查 Agent 登录状态。
        3. 要求 Agent 创建指定文件并写入指定内容。
        4. 检查文件是否存在且内容正确。
        5. 使用 Judge 模型评价 Agent 返回。

    预期结果：
        1. Agent 交互正常完成。
        2. 指定文件在隔离工作目录中创建成功，且内容完全匹配。
        3. Judge 模型判定 Agent 的完成说明正常。
    """

    def test_agent_creates_file_with_requested_content(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge,
    ) -> None:
        self.assert_agent_authenticated(agent_model)
        if not agent_model.capabilities.file_operations:
            pytest.skip("当前 Agent 不支持文件操作")

        file_name = "agent_test_output.txt"
        expected_content = "AgentTestTool file creation passed."
        prompt = (
            f"请在当前工作目录创建文件 {file_name}，文件内容必须恰好为："
            f"{expected_content} 完成后请简短确认。"
        )
        turn = agent_model.send_prompt(prompt)
        self.assert_turn_completed(turn)

        output_file = agent_model.workspace / file_name
        assert output_file.is_file(), f"Agent 未创建文件：{output_file}"
        actual_content = output_file.read_text(encoding="utf-8").strip()
        assert actual_content == expected_content

        verdict = judge_model.evaluate(
            prompt=prompt,
            turn=turn,
            criterion=(
                "Agent 的返回应明确表示已经完成文件创建任务，且不包含报错、"
                "拒绝执行或要求用户自行创建文件等失败信息。"
            ),
        )
        assert verdict.passed, verdict.reason
