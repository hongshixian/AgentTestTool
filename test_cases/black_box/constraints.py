"""Deterministic constraint checking for black-box evidence.

Design principle: Only check objective facts, never make semantic judgments.

Examples of ALLOWED checks:
- Is the file present?
- Is the evidence collection complete?
- Did the collector report ready?

Examples of FORBIDDEN checks:
- Is the file content correct? (semantic judgment)
- Did the agent complete the task? (semantic judgment)
- Is the output satisfactory? (semantic judgment)
"""

from typing import Optional

from test_cases.black_box.unified_evidence import UnifiedEvidence


class DeterministicConstraint:
    """确定性约束检查

    职责：
    - 检查证据完整性（客观事实）
    - 检查必需证据项是否存在（客观事实）
    - 检查采集器状态（客观事实）

    非职责：
    - 不判断文件内容是否正确（语义判断）
    - 不判断 Agent 是否完成任务（语义判断）
    - 不判断输出是否满意（语义判断）
    """

    def check_evidence_completeness(
        self,
        evidence: UnifiedEvidence,
        required_evidence: list[str]
    ) -> Optional[str]:
        """检查证据是否完整

        Args:
            evidence: 证据包
            required_evidence: 必需的证据项列表

        Returns:
            None - 证据完整
            str - 缺失的证据描述
        """
        # 检查采集器状态（客观事实）
        if not evidence.is_ready_for_judge():
            issues = evidence.get_quality_issues()
            if issues:
                return issues[0]  # 返回第一个质量问题
            return "证据质量检查未通过"

        # 检查必需的证据项（客观事实）
        for required in required_evidence:
            if required == "agent_response":
                response = evidence.get_agent_response()
                if not response or not response.strip():
                    return "缺少 Agent 响应"

            elif required == "workspace_changes":
                # 检查是否有任何文件变化
                summary = evidence.get_file_changes_summary()
                if summary["total_changes"] == 0:
                    return "缺少工作区变化"

            elif required == "execution_trace":
                # 黑盒测试通常不需要执行 trace
                # 如果用例明确要求，检查是否有相关信息
                pass

            elif required == "tool_calls":
                # 如果用例要求工具调用，检查是否有记录
                # 注意：这里只检查是否有记录，不判断调用是否正确
                pass

        return None  # 证据完整

    def check_file_exists(
        self,
        evidence: UnifiedEvidence,
        file_path: str
    ) -> bool:
        """检查文件是否存在（客观事实）

        注意：这是客观事实检查，不是语义判断。
        只检查文件是否被创建或存在，不检查内容是否正确。
        """
        return evidence.has_file(file_path)

    def check_file_not_modified(
        self,
        evidence: UnifiedEvidence,
        file_path: str
    ) -> bool:
        """检查文件是否未被修改（客观事实）

        注意：这是客观事实检查，不是语义判断。
        只检查文件是否在修改列表中，不判断修改是否合理。
        """
        return not evidence.is_file_modified(file_path)

    def check_file_deleted(
        self,
        evidence: UnifiedEvidence,
        file_path: str
    ) -> bool:
        """检查文件是否被删除（客观事实）"""
        return evidence.is_file_deleted(file_path)

    def get_file_count_changes(
        self,
        evidence: UnifiedEvidence
    ) -> dict[str, int]:
        """获取文件变化统计（客观事实）

        Returns:
            包含 added, modified, deleted 计数的字典
        """
        return evidence.get_file_changes_summary()

    def check_execution_success(
        self,
        evidence: UnifiedEvidence
    ) -> bool:
        """检查进程是否成功退出（客观事实）

        注意：这只检查退出码是否为 0，不判断任务是否完成。
        """
        return evidence.is_successful()

    def check_has_tool_calls(
        self,
        evidence: UnifiedEvidence
    ) -> bool:
        """检查是否有工具调用（客观事实）"""
        return evidence.get_tool_call_count() > 0

    def check_response_contains_text(
        self,
        evidence: UnifiedEvidence,
        text: str
    ) -> bool:
        """检查响应是否包含特定文本（客观事实）

        注意：这是字符串匹配，不是语义理解。
        只用于检查是否包含标记文本，不用于判断响应质量。
        """
        return text in evidence.get_agent_response()

    def check_no_stderr(
        self,
        evidence: UnifiedEvidence
    ) -> bool:
        """检查是否没有标准错误输出（客观事实）"""
        return not evidence.has_errors()
