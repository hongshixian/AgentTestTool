"""单元测试：EvidenceBundle → UnifiedEvidence 适配器"""

from datetime import datetime
from pathlib import Path

import pytest

from test_cases.black_box.evidence_adapters import adapt_evidence_bundle_to_unified
from test_cases.black_box.evidence_models import (
    EvidenceBundle,
    ExecutionPhase,
    FileRecord,
    WorkspaceSnapshot,
)


def test_adapt_basic_evidence_bundle():
    """测试基本的 EvidenceBundle 适配"""

    # 创建测试用的 EvidenceBundle
    file1 = FileRecord(
        path="output/result.txt",
        content="test content",
        content_hash="abc123",
        size_bytes=12,
        modified_time=datetime.now()
    )

    snapshot = WorkspaceSnapshot(
        before={},
        after={"output/result.txt": file1}
    )

    bundle = EvidenceBundle(
        run_id="test_run_001",
        case_id="T001",
        timestamp=datetime.now(),
        prompt="test prompt",
        agent_response="test response",
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

    # 执行适配
    unified = adapt_evidence_bundle_to_unified(bundle)

    # 验证基本信息
    assert unified.get_case_id() == "T001"
    assert unified.get_run_id() == "test_run_001"
    assert unified.get_prompt() == "test prompt"
    assert unified.get_agent_response() == "test response"
    assert unified.get_execution_time() == 5.0
    assert unified.is_successful()

    # 验证文件变化
    assert unified.has_file("output/result.txt")
    assert unified.get_files_added() == ("output/result.txt",)
    assert unified.get_files_modified() == ()
    assert unified.get_files_deleted() == ()

    # 验证证据质量
    assert unified.is_ready_for_judge()
    assert unified.get_quality_issues() == []


def test_adapt_evidence_with_execution_phases():
    """测试带执行阶段的 EvidenceBundle 适配"""

    snapshot = WorkspaceSnapshot(before={}, after={})

    phase1 = ExecutionPhase(
        phase_id="preview",
        response="preview response",
        duration_seconds=2.0,
        waiting_for_approval=True,
        approval_granted=True
    )

    phase2 = ExecutionPhase(
        phase_id="execute",
        response="execute response",
        duration_seconds=3.0,
        waiting_for_approval=False,
        approval_granted=False
    )

    bundle = EvidenceBundle(
        run_id="test_run_002",
        case_id="T002",
        timestamp=datetime.now(),
        prompt="test prompt",
        agent_response="final response",
        exit_code=0,
        stdout="",
        stderr="",
        execution_time_seconds=5.0,
        workspace_snapshot=snapshot,
        files_added=[],
        files_modified=[],
        files_deleted=[],
        tool_calls=[],
        execution_phases=[phase1, phase2],
        collector_ready=True,
        collection_complete=True,
        positive_control_ok=True
    )

    unified = adapt_evidence_bundle_to_unified(bundle)

    assert unified.get_case_id() == "T002"
    assert unified.get_agent_response() == "final response"


def test_adapt_evidence_with_file_modifications():
    """测试带文件修改的 EvidenceBundle 适配"""

    file_before = FileRecord(
        path="config.txt",
        content="old content",
        content_hash="hash1",
        size_bytes=11,
        modified_time=datetime.now()
    )

    file_after = FileRecord(
        path="config.txt",
        content="new content",
        content_hash="hash2",
        size_bytes=11,
        modified_time=datetime.now()
    )

    snapshot = WorkspaceSnapshot(
        before={"config.txt": file_before},
        after={"config.txt": file_after}
    )

    bundle = EvidenceBundle(
        run_id="test_run_003",
        case_id="T003",
        timestamp=datetime.now(),
        prompt="modify config",
        agent_response="done",
        exit_code=0,
        stdout="",
        stderr="",
        execution_time_seconds=3.0,
        workspace_snapshot=snapshot,
        files_added=[],
        files_modified=[file_after],
        files_deleted=[],
        tool_calls=[],
        collector_ready=True,
        collection_complete=True,
        positive_control_ok=True
    )

    unified = adapt_evidence_bundle_to_unified(bundle)

    assert unified.has_file("config.txt")
    assert unified.is_file_modified("config.txt")
    assert not unified.is_file_deleted("config.txt")
    assert unified.get_files_modified() == ("config.txt",)


def test_adapt_evidence_with_deleted_files():
    """测试带文件删除的 EvidenceBundle 适配"""

    file_before = FileRecord(
        path="temp.txt",
        content="temp content",
        content_hash="hash1",
        size_bytes=12,
        modified_time=datetime.now()
    )

    snapshot = WorkspaceSnapshot(
        before={"temp.txt": file_before},
        after={}
    )

    bundle = EvidenceBundle(
        run_id="test_run_004",
        case_id="T004",
        timestamp=datetime.now(),
        prompt="delete temp file",
        agent_response="deleted",
        exit_code=0,
        stdout="",
        stderr="",
        execution_time_seconds=2.0,
        workspace_snapshot=snapshot,
        files_added=[],
        files_modified=[],
        files_deleted=["temp.txt"],
        tool_calls=[],
        collector_ready=True,
        collection_complete=True,
        positive_control_ok=True
    )

    unified = adapt_evidence_bundle_to_unified(bundle)

    assert unified.is_file_deleted("temp.txt")
    assert unified.get_files_deleted() == ("temp.txt",)


def test_adapt_evidence_with_quality_issues():
    """测试带证据质量问题的 EvidenceBundle 适配"""

    snapshot = WorkspaceSnapshot(before={}, after={})

    bundle = EvidenceBundle(
        run_id="test_run_005",
        case_id="T005",
        timestamp=datetime.now(),
        prompt="test",
        agent_response="response",
        exit_code=0,
        stdout="",
        stderr="",
        execution_time_seconds=1.0,
        workspace_snapshot=snapshot,
        files_added=[],
        files_modified=[],
        files_deleted=[],
        tool_calls=[],
        collector_ready=False,  # 采集器未就绪
        collection_complete=True,
        positive_control_ok=True
    )

    unified = adapt_evidence_bundle_to_unified(bundle)

    assert not unified.is_ready_for_judge()
    issues = unified.get_quality_issues()
    assert len(issues) > 0
    assert "采集器未就绪" in issues[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
