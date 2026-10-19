"""Mock test for end-to-end Judge integration flow."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from agent_models.result import TurnResult
from assertions.judge.model import JudgeConfig, OpenAICompatibleJudge
from assertions.outcome import AssessmentStatus
from test_cases.black_box.assertion import BlackBoxAssertion
from test_cases.black_box.evidence_models import JudgeCriterion
from test_cases.black_box.models import (
    BlackBoxCaseSpec,
    BlackBoxEvidence,
    ControlObservation,
    FileObservation,
    JudgeCriterionSpec,
    PublicObservation,
    PublicStepSpec,
    PublicTurnObservation,
    WorkspaceFileSpec,
)
from agent_models.environment.workspace import WorkspaceSnapshot


def test_black_box_assertion_with_judge_criterion():
    """测试使用 judge_criterion 的黑盒断言"""

    # 创建包含 judge_criterion 的用例规格
    judge_criterion_spec = JudgeCriterionSpec(
        case_id="TEST001",
        title="测试用例",
        description="验证 Agent 是否正确完成任务",
        pass_criteria="1. Agent 创建了输出文件\n2. 输出内容正确",
        fail_criteria="1. 未创建输出文件\n2. 输出内容错误",
        required_evidence=("agent_response", "workspace_changes")
    )

    spec = BlackBoxCaseSpec(
        case_id="TEST001",
        title="测试用例",
        repeat_count=1,
        timeout_seconds=120.0,
        steps=(PublicStepSpec(
            phase_id="exercise",
            prompt="创建测试文件",
            allow_tools=True,
            permission_policy="allow_workspace_edits"
        ),),
        workspace_files=(),
        judge_criterion=judge_criterion_spec,
    )

    # 创建证据（模拟 Agent 成功执行）
    turn = PublicTurnObservation(
        phase_id="exercise",
        response="已创建测试文件",
        returncode=0,
        completed=True,
        duration_seconds=5.0,
        session_id="session_001"
    )

    # 创建空的 workspace snapshot
    empty_snapshot = WorkspaceSnapshot(entries=[])
    after_snapshot = WorkspaceSnapshot(entries=[])  # 简化：实际应该包含文件条目

    evidence = BlackBoxEvidence(
        public=PublicObservation(
            turns=(turn,),
            output_text="已创建测试文件",
            public_objects=[],
            attachments=[]
        ),
        files=FileObservation(
            before=empty_snapshot,
            after=after_snapshot,
            added=frozenset(["output/test.txt"]),
            modified=frozenset(),
            deleted=frozenset()
        ),
        control=ControlObservation(
            run_id="test_run_001",
            case_id="TEST001",
            repeat_index=1,
            collector_ready=True,
            positive_control_ok=True,
            collection_complete=True,
            dropped_event_count=0
        ),
        business_state_before={},
        business_state_after={},
        metrics={}
    )

    # Mock Judge 模型
    mock_judge = Mock(spec=OpenAICompatibleJudge)

    # Mock Judge 返回 PASS
    mock_verdict = Mock()
    mock_verdict.status.name = "PASS"
    mock_verdict.reason = "Agent 正确完成了任务"
    mock_judge.evaluate.return_value = mock_verdict

    # 创建断言对象
    assertion = BlackBoxAssertion(judge_model=mock_judge)

    # 执行评估
    verdict = assertion.evaluate(spec, evidence)

    # 验证结果
    assert verdict.status == AssessmentStatus.PASS
    assert "Judge 评审通过" in verdict.reason
    assert mock_judge.evaluate.called


def test_black_box_assertion_fallback_to_rules():
    """测试没有 judge_criterion 时 fallback 到 assertion_rules"""

    from test_cases.black_box.models import AssertionRule

    # 创建没有 judge_criterion 的用例规格
    spec = BlackBoxCaseSpec(
        case_id="TEST002",
        title="测试用例2",
        repeat_count=1,
        timeout_seconds=120.0,
        steps=(PublicStepSpec(
            phase_id="exercise",
            prompt="测试",
            allow_tools=True
        ),),
        workspace_files=(),
        assertion_rules=(
            AssertionRule(
                metric="Workspace_Change_Count",
                operator="gt",
                expected=0
            ),
        ),
        judge_criterion=None,  # 没有 judge_criterion
    )

    # 创建证据
    turn = PublicTurnObservation(
        phase_id="exercise",
        response="完成",
        returncode=0,
        completed=True,
        duration_seconds=5.0,
        session_id="session_001"
    )

    empty_snapshot = WorkspaceSnapshot(entries=[])

    evidence = BlackBoxEvidence(
        public=PublicObservation(
            turns=(turn,),
            output_text="完成",
            public_objects=[],
            attachments=[]
        ),
        files=FileObservation(
            before=empty_snapshot,
            after=empty_snapshot,
            added=frozenset(["output/test.txt"]),
            modified=frozenset(),
            deleted=frozenset()
        ),
        control=ControlObservation(
            run_id="test_run_002",
            case_id="TEST002",
            repeat_index=1,
            collector_ready=True,
            positive_control_ok=True,
            collection_complete=True,
            dropped_event_count=0
        ),
        business_state_before={},
        business_state_after={},
        metrics={}
    )

    # 创建断言对象（不传 judge_model）
    assertion = BlackBoxAssertion(judge_model=None)

    # 执行评估
    verdict = assertion.evaluate(spec, evidence)

    # 验证使用了旧的断言逻辑
    assert verdict.status == AssessmentStatus.PASS
    assert "黑盒断言全部满足" in verdict.reason


def test_evidence_incompleteness():
    """测试证据不完整的情况"""

    judge_criterion_spec = JudgeCriterionSpec(
        case_id="TEST003",
        title="测试用例3",
        description="测试",
        pass_criteria="通过",
        fail_criteria="失败",
        required_evidence=("agent_response", "workspace_changes")
    )

    spec = BlackBoxCaseSpec(
        case_id="TEST003",
        title="测试用例3",
        repeat_count=1,
        timeout_seconds=120.0,
        steps=(),
        workspace_files=(),
        judge_criterion=judge_criterion_spec,
    )

    # 创建证据不完整的情况
    empty_snapshot = WorkspaceSnapshot(entries=[])

    evidence = BlackBoxEvidence(
        public=PublicObservation(
            turns=(),
            output_text="",
            public_objects=[],
            attachments=[]
        ),
        files=FileObservation(
            before=empty_snapshot,
            after=empty_snapshot,
            added=frozenset(),
            modified=frozenset(),
            deleted=frozenset()
        ),
        control=ControlObservation(
            run_id="test_run_003",
            case_id="TEST003",
            repeat_index=1,
            collector_ready=False,  # 采集器未就绪
            positive_control_ok=True,
            collection_complete=False,  # 采集未完成
            dropped_event_count=0
        ),
        business_state_before={},
        business_state_after={},
        metrics={}
    )

    # 创建断言对象
    assertion = BlackBoxAssertion(judge_model=None)

    # 执行评估
    verdict = assertion.evaluate(spec, evidence)

    # 验证结果为 INCONCLUSIVE
    assert verdict.status == AssessmentStatus.INCONCLUSIVE
    assert "证据采集未完整闭合" in verdict.reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
