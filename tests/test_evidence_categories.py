"""单元测试：证据类别定义"""

from datetime import datetime
from pathlib import Path

import pytest

from agent_models.environment.workspace import WorkspaceEntry, WorkspaceSnapshot
from test_cases.black_box.evidence_categories import (
    AgentTrace,
    BusinessStateChanges,
    CollectionMetadata,
    ComputedMetrics,
    ExecutionContext,
    FileDisplayInfo,
    FilesystemChanges,
    PhaseRecord,
    SideEffects,
    ToolCallRecord,
    ToolStateChanges,
    TurnRecord,
)


# ========================================
# ExecutionContext 测试
# ========================================

def test_execution_context_creation():
    """测试 ExecutionContext 的创建"""
    ctx = ExecutionContext(
        run_id="test_run_001",
        case_id="B001",
        repeat_index=1,
        timestamp=datetime.now()
    )
    assert ctx.run_id == "test_run_001"
    assert ctx.case_id == "B001"
    assert ctx.repeat_index == 1


def test_execution_context_validation():
    """测试 ExecutionContext 的验证"""
    with pytest.raises(ValueError, match="run_id"):
        ExecutionContext("", "B001", 1, datetime.now())

    with pytest.raises(ValueError, match="case_id"):
        ExecutionContext("run1", "", 1, datetime.now())

    with pytest.raises(ValueError, match="repeat_index"):
        ExecutionContext("run1", "B001", 0, datetime.now())


# ========================================
# AgentTrace 测试
# ========================================

def test_turn_record_creation():
    """测试 TurnRecord 的创建"""
    turn = TurnRecord(
        phase_id="exercise",
        prompt="test prompt",
        response="test response",
        completed=True,
        returncode=0,
        duration_seconds=5.0,
        session_id="session_001"
    )
    assert turn.phase_id == "exercise"
    assert turn.completed is True


def test_agent_trace_creation():
    """测试 AgentTrace 的创建"""
    turn = TurnRecord("exercise", "prompt", "response", True, 0, 5.0)
    trace = AgentTrace(
        prompt="test prompt",
        turns=(turn,),
        final_response="response",
        execution_phases=None,
        exit_code=0,
        duration_seconds=5.0,
        stdout="",
        stderr=""
    )
    assert trace.prompt == "test prompt"
    assert len(trace.turns) == 1
    assert trace.exit_code == 0


def test_agent_trace_validation():
    """测试 AgentTrace 的验证"""
    with pytest.raises(ValueError, match="turns"):
        AgentTrace(
            prompt="test",
            turns=(),  # 空 turns
            final_response="",
            execution_phases=None,
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr=""
        )


# ========================================
# FilesystemChanges 测试
# ========================================

def test_filesystem_changes_get_file_content():
    """测试 FilesystemChanges.get_file_content()"""
    entry = WorkspaceEntry("test.txt", False, 0o644, b"hello", "hash123")
    snapshot_after = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, (entry,))
    snapshot_before = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, ())

    fs = FilesystemChanges(
        before_snapshot=snapshot_before,
        after_snapshot=snapshot_after,
        added=("test.txt",),
        modified=(),
        deleted=()
    )

    content = fs.get_file_content("test.txt")
    assert content == b"hello"


def test_filesystem_changes_has_file():
    """测试 FilesystemChanges.has_file()"""
    entry = WorkspaceEntry("test.txt", False, 0o644, b"hello", "hash123")
    snapshot_after = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, (entry,))
    snapshot_before = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, ())

    fs = FilesystemChanges(
        before_snapshot=snapshot_before,
        after_snapshot=snapshot_after,
        added=("test.txt",),
        modified=(),
        deleted=()
    )

    assert fs.has_file("test.txt")
    assert not fs.has_file("nonexistent.txt")


def test_filesystem_changes_to_display_format():
    """测试 FilesystemChanges.to_display_format()"""
    entry = WorkspaceEntry("test.txt", False, 0o644, b"hello", "hash123")
    snapshot_after = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, (entry,))
    snapshot_before = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, ())

    fs = FilesystemChanges(
        before_snapshot=snapshot_before,
        after_snapshot=snapshot_after,
        added=("test.txt",),
        modified=(),
        deleted=()
    )

    display = fs.to_display_format()
    assert "test.txt" in display
    assert display["test.txt"].size_bytes == 5
    assert display["test.txt"].content == "hello"


def test_file_display_info_describe_omitted():
    """测试 FileDisplayInfo.describe_omitted()"""
    # 文本文件不需要说明
    info1 = FileDisplayInfo(
        path="test.txt",
        size_bytes=100,
        content="hello",
        content_hash="hash",
        modified_time=datetime.now(),
        encoding="utf-8",
        content_omitted_reason=None,
        extracted_text=None
    )
    assert info1.describe_omitted() == ""

    # 二进制文件需要说明
    info2 = FileDisplayInfo(
        path="test.bin",
        size_bytes=100,
        content=None,
        content_hash="hash",
        modified_time=datetime.now(),
        encoding=None,
        content_omitted_reason="二进制文件",
        extracted_text=None
    )
    desc = info2.describe_omitted()
    assert "二进制文件" in desc
    assert "100 字节" in desc


# ========================================
# ToolStateChanges 测试
# ========================================

def test_tool_state_changes_get_call_count():
    """测试 ToolStateChanges.get_call_count()"""
    call1 = ToolCallRecord("tool1", {}, None, datetime.now())
    call2 = ToolCallRecord("tool1", {}, None, datetime.now())
    call3 = ToolCallRecord("tool2", {}, None, datetime.now())

    tool_state = ToolStateChanges(
        before={},
        after={},
        tool_calls=(call1, call2, call3)
    )

    assert tool_state.get_call_count("tool1") == 2
    assert tool_state.get_call_count("tool2") == 1
    assert tool_state.get_call_count("tool3") == 0


def test_tool_state_changes_get_state_delta():
    """测试 ToolStateChanges.get_state_delta()"""
    tool_state = ToolStateChanges(
        before={"a": 1, "b": 2},
        after={"a": 1, "b": 3, "c": 4},
        tool_calls=()
    )

    delta = tool_state.get_state_delta()
    assert delta == {
        "b": (2, 3),
        "c": (None, 4)
    }


# ========================================
# CollectionMetadata 测试
# ========================================

def test_collection_metadata_is_ready():
    """测试 CollectionMetadata.is_ready_for_judge()"""
    meta = CollectionMetadata(True, True, True, 0)
    assert meta.is_ready_for_judge()
    assert meta.get_quality_issues() == []


def test_collection_metadata_has_issues():
    """测试 CollectionMetadata.get_quality_issues()"""
    meta = CollectionMetadata(False, True, True, 2)
    assert not meta.is_ready_for_judge()
    issues = meta.get_quality_issues()
    assert "采集器未就绪" in issues
    assert "丢弃了 2 个事件" in issues


def test_collection_metadata_validation():
    """测试 CollectionMetadata 的验证"""
    with pytest.raises(ValueError, match="dropped_event_count"):
        CollectionMetadata(True, True, True, -1)


# ========================================
# ComputedMetrics 测试
# ========================================

def test_computed_metrics_get_metric():
    """测试 ComputedMetrics.get_metric()"""
    metrics = ComputedMetrics(
        framework_computed={"completed": 1},
        agent_submitted={"owner": "林舟"}
    )

    # Agent 提交的指标优先
    assert metrics.get_metric("owner") == "林舟"
    assert metrics.get_metric("completed") == 1
    assert metrics.get_metric("nonexistent") is None


def test_computed_metrics_has_metric():
    """测试 ComputedMetrics.has_metric()"""
    metrics = ComputedMetrics(
        framework_computed={"completed": 1},
        agent_submitted={"owner": "林舟"}
    )

    assert metrics.has_metric("owner")
    assert metrics.has_metric("completed")
    assert not metrics.has_metric("nonexistent")


def test_computed_metrics_get_all_metrics():
    """测试 ComputedMetrics.get_all_metrics()"""
    metrics = ComputedMetrics(
        framework_computed={"completed": 1, "returncode": 0},
        agent_submitted={"owner": "林舟"}
    )

    all_metrics = metrics.get_all_metrics()
    assert all_metrics == {
        "completed": 1,
        "returncode": 0,
        "owner": "林舟"
    }


# ========================================
# SideEffects 测试
# ========================================

def test_side_effects_creation():
    """测试 SideEffects 的创建"""
    entry = WorkspaceEntry("test.txt", False, 0o644, b"hello", "hash123")
    snapshot_after = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, (entry,))
    snapshot_before = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, ())

    filesystem = FilesystemChanges(
        before_snapshot=snapshot_before,
        after_snapshot=snapshot_after,
        added=("test.txt",),
        modified=(),
        deleted=()
    )

    tool_state = ToolStateChanges(
        before={},
        after={},
        tool_calls=()
    )

    business_state = BusinessStateChanges(
        before={},
        after={}
    )

    side_effects = SideEffects(
        filesystem=filesystem,
        tool_state=tool_state,
        business_state=business_state,
        public_objects=(),
        attachments=()
    )

    assert side_effects.filesystem is filesystem
    assert side_effects.tool_state is tool_state
    assert side_effects.business_state is business_state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
