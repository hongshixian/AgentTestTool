"""单元测试：UnifiedEvidence 统一证据容器"""

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
    FilesystemChanges,
    SideEffects,
    ToolStateChanges,
    TurnRecord,
)
from test_cases.black_box.unified_evidence import UnifiedEvidence


def create_test_evidence() -> UnifiedEvidence:
    """创建测试用的 UnifiedEvidence"""

    # 1. 执行上下文
    context = ExecutionContext(
        run_id="test_run_001",
        case_id="B001",
        repeat_index=1,
        timestamp=datetime.now()
    )

    # 2. Agent 轨迹
    turn = TurnRecord("exercise", "test prompt", "test response", True, 0, 5.0)
    trace = AgentTrace(
        prompt="test prompt",
        turns=(turn,),
        final_response="test response",
        execution_phases=None,
        exit_code=0,
        duration_seconds=5.0,
        stdout="",
        stderr=""
    )

    # 3. 副作用
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

    # 4. 采集元数据
    collection = CollectionMetadata(
        collector_ready=True,
        collection_complete=True,
        positive_control_ok=True,
        dropped_event_count=0
    )

    # 5. 计算指标
    metrics = ComputedMetrics(
        framework_computed={"completed": 1},
        agent_submitted={"owner": "林舟"}
    )

    return UnifiedEvidence(
        _context=context,
        _trace=trace,
        _side_effects=side_effects,
        _collection=collection,
        _metrics=metrics
    )


# ========================================
# 状态查询接口测试
# ========================================

def test_unified_evidence_is_ready_for_judge():
    """测试 is_ready_for_judge()"""
    evidence = create_test_evidence()
    assert evidence.is_ready_for_judge()


def test_unified_evidence_get_quality_issues():
    """测试 get_quality_issues()"""
    evidence = create_test_evidence()
    assert evidence.get_quality_issues() == []


def test_unified_evidence_is_successful():
    """测试 is_successful()"""
    evidence = create_test_evidence()
    assert evidence.is_successful()


def test_unified_evidence_has_errors():
    """测试 has_errors()"""
    evidence = create_test_evidence()
    assert not evidence.has_errors()


def test_unified_evidence_has_file():
    """测试 has_file()"""
    evidence = create_test_evidence()
    assert evidence.has_file("test.txt")
    assert not evidence.has_file("nonexistent.txt")


def test_unified_evidence_is_file_modified():
    """测试 is_file_modified()"""
    evidence = create_test_evidence()
    assert not evidence.is_file_modified("test.txt")


def test_unified_evidence_is_file_deleted():
    """测试 is_file_deleted()"""
    evidence = create_test_evidence()
    assert not evidence.is_file_deleted("test.txt")


# ========================================
# 数据访问接口测试
# ========================================

def test_unified_evidence_get_case_id():
    """测试 get_case_id()"""
    evidence = create_test_evidence()
    assert evidence.get_case_id() == "B001"


def test_unified_evidence_get_run_id():
    """测试 get_run_id()"""
    evidence = create_test_evidence()
    assert evidence.get_run_id() == "test_run_001"


def test_unified_evidence_get_repeat_index():
    """测试 get_repeat_index()"""
    evidence = create_test_evidence()
    assert evidence.get_repeat_index() == 1


def test_unified_evidence_get_prompt():
    """测试 get_prompt()"""
    evidence = create_test_evidence()
    assert evidence.get_prompt() == "test prompt"


def test_unified_evidence_get_agent_response():
    """测试 get_agent_response()"""
    evidence = create_test_evidence()
    assert evidence.get_agent_response() == "test response"


def test_unified_evidence_get_all_turns():
    """测试 get_all_turns()"""
    evidence = create_test_evidence()
    turns = evidence.get_all_turns()
    assert len(turns) == 1
    assert turns[0].phase_id == "exercise"
    assert turns[0].completed


def test_unified_evidence_get_execution_time():
    """测试 get_execution_time()"""
    evidence = create_test_evidence()
    assert evidence.get_execution_time() == 5.0


def test_unified_evidence_get_file_content():
    """测试 get_file_content()"""
    evidence = create_test_evidence()
    content = evidence.get_file_content("test.txt")
    assert content == "hello"


def test_unified_evidence_get_files_added():
    """测试 get_files_added()"""
    evidence = create_test_evidence()
    assert evidence.get_files_added() == ("test.txt",)


def test_unified_evidence_get_files_modified():
    """测试 get_files_modified()"""
    evidence = create_test_evidence()
    assert evidence.get_files_modified() == ()


def test_unified_evidence_get_files_deleted():
    """测试 get_files_deleted()"""
    evidence = create_test_evidence()
    assert evidence.get_files_deleted() == ()


def test_unified_evidence_get_file_changes_summary():
    """测试 get_file_changes_summary()"""
    evidence = create_test_evidence()
    summary = evidence.get_file_changes_summary()
    assert summary["added"] == 1
    assert summary["modified"] == 0
    assert summary["deleted"] == 0
    assert summary["total_changes"] == 1


def test_unified_evidence_get_metric():
    """测试 get_metric()"""
    evidence = create_test_evidence()
    assert evidence.get_metric("owner") == "林舟"
    assert evidence.get_metric("completed") == 1
    assert evidence.get_metric("nonexistent") is None


def test_unified_evidence_has_metric():
    """测试 has_metric()"""
    evidence = create_test_evidence()
    assert evidence.has_metric("owner")
    assert evidence.has_metric("completed")
    assert not evidence.has_metric("nonexistent")


def test_unified_evidence_get_all_metrics():
    """测试 get_all_metrics()"""
    evidence = create_test_evidence()
    metrics = evidence.get_all_metrics()
    assert metrics["owner"] == "林舟"
    assert metrics["completed"] == 1


def test_unified_evidence_get_tool_call_count():
    """测试 get_tool_call_count()"""
    evidence = create_test_evidence()
    assert evidence.get_tool_call_count() == 0
    assert evidence.get_tool_call_count("any_tool") == 0


# ========================================
# 转换导出接口测试
# ========================================

def test_unified_evidence_to_judge_prompt():
    """测试 to_judge_prompt()"""
    evidence = create_test_evidence()
    prompt = evidence.to_judge_prompt()

    # 验证包含关键部分
    assert "## 测试上下文" in prompt
    assert "B001" in prompt
    assert "## 用户 Prompt" in prompt
    assert "test prompt" in prompt
    assert "## Agent 响应" in prompt
    assert "test response" in prompt
    assert "## 工作区变化" in prompt
    assert "test.txt" in prompt


def test_unified_evidence_to_summary_dict():
    """测试 to_summary_dict()"""
    evidence = create_test_evidence()
    summary = evidence.to_summary_dict()

    assert summary["run_id"] == "test_run_001"
    assert summary["case_id"] == "B001"
    assert summary["execution_time_seconds"] == 5.0
    assert summary["exit_code"] == 0
    assert summary["collection_ready"] is True
    assert summary["files_added"] == ["test.txt"]
    assert summary["metrics"]["owner"] == "林舟"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
