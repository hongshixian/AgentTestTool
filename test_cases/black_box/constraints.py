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

from test_cases.black_box.evidence_models import EvidenceBundle


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
        evidence: EvidenceBundle,
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
        if not evidence.collector_ready:
            return "证据采集器未就绪"

        if not evidence.collection_complete:
            return "证据采集未完成"

        if not evidence.positive_control_ok:
            return "正对照检查未通过"

        # 检查必需的证据项（客观事实）
        for required in required_evidence:
            if required == "agent_response":
                if not evidence.agent_response or not evidence.agent_response.strip():
                    return "缺少 Agent 响应"

            elif required == "workspace_changes":
                if evidence.workspace_snapshot is None:
                    return "缺少工作区快照"

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
        evidence: EvidenceBundle,
        file_path: str
    ) -> bool:
        """检查文件是否存在（客观事实）

        注意：这是客观事实检查，不是语义判断。
        只检查文件是否被创建或存在，不检查内容是否正确。
        """
        # 检查是否在新增文件列表中
        if any(f.path == file_path for f in evidence.files_added):
            return True

        # 检查是否在修改文件列表中（说明原本存在）
        if any(f.path == file_path for f in evidence.files_modified):
            return True

        # 检查是否在执行后的快照中
        if file_path in evidence.workspace_snapshot.after:
            return True

        return False

    def check_file_not_modified(
        self,
        evidence: EvidenceBundle,
        file_path: str
    ) -> bool:
        """检查文件是否未被修改（客观事实）

        注意：这是客观事实检查，不是语义判断。
        只检查文件是否在修改列表中，不判断修改是否合理。
        """
        # 检查是否在修改文件列表中
        if any(f.path == file_path for f in evidence.files_modified):
            return False  # 文件被修改了

        # 检查是否在删除文件列表中
        if file_path in evidence.files_deleted:
            return False  # 文件被删除了

        return True  # 文件未被修改

    def check_file_deleted(
        self,
        evidence: EvidenceBundle,
        file_path: str
    ) -> bool:
        """检查文件是否被删除（客观事实）"""
        return file_path in evidence.files_deleted

    def get_file_count_changes(
        self,
        evidence: EvidenceBundle
    ) -> dict[str, int]:
        """获取文件变化统计（客观事实）

        Returns:
            包含 added, modified, deleted 计数的字典
        """
        return {
            "added": len(evidence.files_added),
            "modified": len(evidence.files_modified),
            "deleted": len(evidence.files_deleted),
            "total_changes": len(evidence.files_added) + len(evidence.files_modified) + len(evidence.files_deleted)
        }

    def check_execution_success(
        self,
        evidence: EvidenceBundle
    ) -> bool:
        """检查进程是否成功退出（客观事实）

        注意：这只检查退出码是否为 0，不判断任务是否完成。
        """
        return evidence.exit_code == 0

    def check_has_tool_calls(
        self,
        evidence: EvidenceBundle
    ) -> bool:
        """检查是否有工具调用（客观事实）"""
        return len(evidence.tool_calls) > 0

    def check_response_contains_text(
        self,
        evidence: EvidenceBundle,
        text: str
    ) -> bool:
        """检查响应是否包含特定文本（客观事实）

        注意：这是字符串匹配，不是语义理解。
        只用于检查是否包含标记文本，不用于判断响应质量。
        """
        return text in evidence.agent_response

    def check_no_stderr(
        self,
        evidence: EvidenceBundle
    ) -> bool:
        """检查是否没有标准错误输出（客观事实）"""
        return not evidence.stderr or not evidence.stderr.strip()
