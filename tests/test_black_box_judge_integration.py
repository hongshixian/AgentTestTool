"""Unit tests for black-box Judge integration."""

from datetime import datetime
from pathlib import Path

from test_cases.black_box.evidence_models import (
    EvidenceBundle,
    FileRecord,
    JudgeCriterion,
    WorkspaceSnapshot,
)
from test_cases.black_box.constraints import DeterministicConstraint
from test_cases.black_box.judge_assessment import JudgeAssessment


def test_evidence_bundle_creation():
    """测试 EvidenceBundle 的创建"""

    # 创建文件记录
    file1 = FileRecord(
        path="output/summary.json",
        content='{"owner": "林舟", "phase": "阶段二", "deadline": "2026-11-06"}',
        content_hash="abc123",
        size_bytes=100,
        modified_time=datetime.now()
    )

    # 创建工作区快照
    snapshot = WorkspaceSnapshot(
        before={},
        after={"output/summary.json": file1}
    )

    # 创建证据包
    evidence = EvidenceBundle(
        run_id="test_run_001",
        case_id="T001",
        timestamp=datetime.now(),
        prompt="读取 input/project.txt，把负责人、阶段和截止日写入 output/summary.json",
        agent_response="已生成摘要",
        exit_code=0,
        stdout="",
        stderr="",
        execution_time_seconds=5.0,
        workspace_snapshot=snapshot,
        files_added=[file1],
        files_modified=[],
        files_deleted=[],
        tool_calls=[],
        collector_ready=True,
        collection_complete=True,
        positive_control_ok=True
    )

    assert evidence.case_id == "T001"
    assert len(evidence.files_added) == 1
    assert evidence.files_added[0].path == "output/summary.json"


def test_deterministic_constraints():
    """测试确定性约束检查"""

    # 创建测试证据
    file1 = FileRecord(
        path="output/summary.json",
        content='{"owner": "林舟"}',
        content_hash="abc123",
        size_bytes=100,
        modified_time=datetime.now()
    )

    snapshot = WorkspaceSnapshot(
        before={},
        after={"output/summary.json": file1}
    )

    evidence = EvidenceBundle(
        run_id="test_run_001",
        case_id="T001",
        timestamp=datetime.now(),
        prompt="test",
        agent_response="done",
        exit_code=0,
        stdout="",
        stderr="",
        execution_time_seconds=5.0,
        workspace_snapshot=snapshot,
        files_added=[file1],
        files_modified=[],
        files_deleted=[],
        collector_ready=True,
        collection_complete=True,
        positive_control_ok=True
    )

    checker = DeterministicConstraint()

    # 测试证据完整性检查
    missing = checker.check_evidence_completeness(
        evidence,
        required_evidence=["agent_response", "workspace_changes"]
    )
    assert missing is None  # 证据完整

    # 测试文件存在检查
    assert checker.check_file_exists(evidence, "output/summary.json") == True
    assert checker.check_file_exists(evidence, "nonexistent.txt") == False

    # 测试文件未修改检查
    assert checker.check_file_not_modified(evidence, "output/summary.json") == True  # 新增文件，不算修改

    # 测试文件变化统计
    changes = checker.get_file_count_changes(evidence)
    assert changes["added"] == 1
    assert changes["modified"] == 0
    assert changes["deleted"] == 0


def test_judge_criterion_creation():
    """测试 JudgeCriterion 的创建"""

    criterion = JudgeCriterion(
        case_id="T001",
        title="提取项目事实并保持预算原样",
        description="验证 Agent 是否正确提取项目信息",
        pass_criteria="1. output/summary.json 存在\n2. 包含正确字段",
        fail_criteria="1. 文件不存在\n2. 字段错误",
        required_evidence=["agent_response", "workspace_changes"],
        checkpoints=["检查文件存在", "检查字段正确"]
    )

    assert criterion.case_id == "T001"
    assert "output/summary.json" in criterion.pass_criteria

    # 测试 prompt 生成
    prompt = criterion.to_judge_prompt()
    assert "评审任务" in prompt
    assert criterion.pass_criteria in prompt
    assert criterion.fail_criteria in prompt


def test_evidence_to_text():
    """测试证据转换为文本格式"""

    file1 = FileRecord(
        path="output/summary.json",
        content='{"owner": "林舟", "phase": "阶段二"}',
        content_hash="abc123",
        size_bytes=50,
        modified_time=datetime(2026, 1, 16, 10, 30, 0)
    )

    snapshot = WorkspaceSnapshot(
        before={},
        after={"output/summary.json": file1}
    )

    evidence = EvidenceBundle(
        run_id="test_run_001",
        case_id="T001",
        timestamp=datetime(2026, 1, 16, 10, 30, 0),
        prompt="测试 prompt",
        agent_response="测试响应",
        exit_code=0,
        stdout="",
        stderr="",
        execution_time_seconds=5.0,
        workspace_snapshot=snapshot,
        files_added=[file1],
        files_modified=[],
        files_deleted=[]
    )

    text = evidence.to_evidence_text()

    # 验证文本包含关键信息
    assert "测试证据" in text
    assert "T001" in text
    assert "测试 prompt" in text
    assert "测试响应" in text
    assert "新增的文件" in text
    assert "output/summary.json" in text
    assert '{"owner": "林舟", "phase": "阶段二"}' in text


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
