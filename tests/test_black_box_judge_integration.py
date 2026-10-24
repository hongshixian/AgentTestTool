"""Unit tests for black-box Judge integration."""

from datetime import datetime
from pathlib import Path

from test_cases.black_box.evidence_models import (
    EvidenceBundle,
    FileRecord,
    JudgeCriterion,
    WorkspaceSnapshot,
)
from test_cases.black_box.evidence_adapters import adapt_evidence_bundle_to_unified
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

    # 使用适配器将 EvidenceBundle 转换为 UnifiedEvidence
    unified_evidence = adapt_evidence_bundle_to_unified(evidence)

    # 测试证据完整性检查
    missing = checker.check_evidence_completeness(
        unified_evidence,
        required_evidence=["agent_response", "workspace_changes"]
    )
    assert missing is None  # 证据完整

    # 测试文件存在检查
    assert checker.check_file_exists(unified_evidence, "output/summary.json") == True
    assert checker.check_file_exists(unified_evidence, "nonexistent.txt") == False

    # 测试文件未修改检查
    assert checker.check_file_not_modified(unified_evidence, "output/summary.json") == True  # 新增文件，不算修改

    # 测试文件变化统计
    changes = checker.get_file_count_changes(unified_evidence)
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


def test_binary_file_reports_real_size_not_zero():
    """二进制文件必须报告真实大小，避免 Judge 误判为 0 字节空文件。"""
    from types import SimpleNamespace
    from pathlib import Path
    from test_cases.black_box.judge_assessment import create_evidence_bundle_from_legacy

    xlsx_bytes = b"PK\x03\x04" + b"\x00\xff" * 500  # 非 UTF-8 内容
    prepared = SimpleNamespace(run_id="r1",
                               spec=SimpleNamespace(case_id="T900", steps=[SimpleNamespace(prompt="p")]),
                               workspace_root=Path("/tmp/nonexistent"),
                               positive_control_ok=True)
    result = SimpleNamespace(turns=[], elapsed_seconds=0.0, exit_code=0)
    snapshot = {
        "before": {},
        "after": {"output/quarter.xlsx": {"hash": "h", "size": len(xlsx_bytes),
                                          "mtime": 0, "content": None, "omitted_reason": "二进制文件"}},
    }
    bundle = create_evidence_bundle_from_legacy(prepared, result, snapshot)

    record = bundle.files_added[0]
    assert record.path == "output/quarter.xlsx"
    assert record.size_bytes == len(xlsx_bytes)  # 不是 0
    assert record.content is None
    assert record.content_omitted_reason == "二进制文件"

    text = bundle.to_evidence_text()
    assert "0 字节" not in text.split("output/quarter.xlsx")[-1][:200]
    assert f"实际大小 {len(xlsx_bytes)} 字节" in text
    assert "二进制文件" in text


def test_judge_prompt_uses_real_size_of_binary_snapshot_entry():
    """端到端路径：内存快照里的 xlsx 字节必须以真实大小出现在 Judge 输入中。"""
    import hashlib
    from unittest.mock import Mock
    from assertions.outcome import AssessmentStatus
    from agent_models.environment.workspace import WorkspaceEntry
    from agent_models.environment.workspace import WorkspaceSnapshot as RealSnapshot
    from test_cases.black_box.assertion import BlackBoxAssertion
    from test_cases.black_box.models import (
        BlackBoxCaseSpec, BlackBoxEvidence, ControlObservation, FileObservation,
        JudgeCriterionSpec, PublicObservation, PublicStepSpec, PublicTurnObservation,
    )

    xlsx = (Path(__file__).resolve().parents[1] / "assets/t_series/T053/input/jan.xlsx").read_bytes()
    entry = WorkspaceEntry("output/quarter.xlsx", False, 0o644, xlsx, hashlib.sha256(xlsx).hexdigest())
    before = RealSnapshot(Path("/tmp/ws"), (0, 0), 0o755, ())
    after = RealSnapshot(Path("/tmp/ws"), (0, 0), 0o755, (entry,))
    turn = PublicTurnObservation("exercise", "完成", 0, True, 1.0, "s1")
    evidence = BlackBoxEvidence(
        PublicObservation((turn,), "完成", (), ()),
        FileObservation(before, after, ("output/quarter.xlsx",), (), ()),
        ControlObservation("r1", "T053", 1, True, True, True),
        {}, {}, {},
    )
    spec = BlackBoxCaseSpec(
        case_id="T053", title="合并明细", repeat_count=1, timeout_seconds=1200.0,
        steps=(PublicStepSpec("exercise", "合并", True, "allow_workspace_edits"),),
        workspace_files=(),
        judge_criterion=JudgeCriterionSpec("T053", "合并明细", "d", "通过", "失败",
                                           ("agent_response", "workspace_changes")),
    )
    judge = Mock()
    judge.evaluate.return_value = Mock(status=Mock(name="PASS"), reason="ok")
    judge.evaluate.return_value.status.name = "PASS"

    verdict = BlackBoxAssertion(judge_model=judge).evaluate(spec, evidence)

    assert verdict.status is AssessmentStatus.PASS
    prompt = judge.evaluate.call_args.kwargs["prompt"]
    section = prompt.split("### 文件: output/quarter.xlsx")[1][:400]
    assert f"大小: {len(xlsx)} 字节" in section
    assert f"实际大小 {len(xlsx)} 字节" in section
    assert "二进制文件" in section
    assert "大小: 0 字节" not in section
