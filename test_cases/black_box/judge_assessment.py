"""Judge assessment layer for black-box testing.

Design principle: All semantic judgments are made by Judge, not by the framework.
"""

import json
from typing import Optional

from assertions.judge.model import OpenAICompatibleJudge
from assertions.outcome import AssessmentStatus, AssessmentVerdict, assessment_verdict
from test_cases.black_box.constraints import DeterministicConstraint
from test_cases.black_box.evidence_models import EvidenceBundle, JudgeCriterion


class JudgeAssessment:
    """Judge 评审层

    职责：
    - 将黑盒证据转换为 Judge 可以理解的格式
    - 调用 Judge API 进行语义判断
    - 转换 Judge 结果为测评结论

    设计原则：
    - 框架只做确定性检查（证据完整性）
    - 所有语义判断由 Judge 完成
    """

    def __init__(self, judge_model: OpenAICompatibleJudge):
        self.judge = judge_model
        self.constraint_checker = DeterministicConstraint()

    def evaluate(
        self,
        evidence: EvidenceBundle,
        criterion: JudgeCriterion
    ) -> AssessmentVerdict:
        """执行完整评审流程

        流程：
        1. 确定性检查：证据是否完整
        2. 调用 Judge：做语义判断
        3. 转换结果：Judge verdict → Assessment verdict

        Args:
            evidence: 黑盒测试证据包
            criterion: Judge 评审标准

        Returns:
            测评结论（PASS/FAIL/INCONCLUSIVE）
        """
        # 步骤 1：确定性检查 - 证据完整性
        missing = self.constraint_checker.check_evidence_completeness(
            evidence,
            criterion.required_evidence
        )
        if missing:
            return assessment_verdict(
                AssessmentStatus.INCONCLUSIVE,
                reason=f"{criterion.case_id} 证据不足：{missing}"
            )

        # 步骤 2：调用 Judge 做语义判断
        try:
            judge_verdict = self._call_judge(evidence, criterion)
        except Exception as e:
            # Judge 调用失败
            return assessment_verdict(
                AssessmentStatus.FAIL,
                reason=f"{criterion.case_id} Judge 调用失败：{type(e).__name__}: {str(e)}"
            )

        # 步骤 3：转换 Judge 结果到测评结论
        return self._convert_judge_verdict(judge_verdict, criterion.case_id)

    def _call_judge(
        self,
        evidence: EvidenceBundle,
        criterion: JudgeCriterion
    ) -> dict:
        """调用 Judge API 进行评审

        使用简化的 evaluate() 接口，不使用复杂的 evaluate_evidence()
        """
        # 准备证据文本
        evidence_text = evidence.to_evidence_text()

        # 准备评审标准
        criterion_prompt = criterion.to_judge_prompt()

        # 构造完整的 Judge prompt
        full_prompt = f"{criterion_prompt}\n\n{evidence_text}"

        # 调用 Judge（使用简化接口）
        # 创建一个假的 TurnResult 来适配现有接口
        from agent_models.result import TurnResult

        fake_turn = TurnResult(
            response=evidence_text,
            raw_output="",
            stderr="",
            completed=True
        )

        judge_verdict = self.judge.evaluate(
            prompt=full_prompt,
            turn=fake_turn,
            criterion=f"{criterion.pass_criteria}\n\n失败条件：\n{criterion.fail_criteria}"
        )

        # 转换为字典格式
        return {
            "verdict": "PASS" if judge_verdict.status.name == "PASS" else "FAIL",
            "reason": judge_verdict.reason
        }

    def _convert_judge_verdict(
        self,
        judge_result: dict,
        case_id: str
    ) -> AssessmentVerdict:
        """转换 Judge 结果到测评结论

        Args:
            judge_result: Judge 返回的判定结果
            case_id: 用例 ID

        Returns:
            测评结论
        """
        verdict = judge_result.get("verdict", "").upper()
        reason = judge_result.get("reason", "无理由")

        if verdict == "PASS":
            return assessment_verdict(
                AssessmentStatus.PASS,
                reason=f"{case_id} Judge 评审通过：{reason}"
            )
        elif verdict == "FAIL":
            return assessment_verdict(
                AssessmentStatus.FAIL,
                reason=f"{case_id} Judge 评审不通过：{reason}"
            )
        else:
            # Judge 无法判断或返回了其他状态
            return assessment_verdict(
                AssessmentStatus.INCONCLUSIVE,
                reason=f"{case_id} Judge 无法判断：{reason}"
            )


def create_evidence_bundle_from_legacy(
    prepared,
    result,
    files_snapshot: dict
) -> EvidenceBundle:
    """从旧的证据格式转换为新的 EvidenceBundle

    这是过渡期的适配函数，用于重构期间保持兼容性。

    Args:
        prepared: PreparedScenario
        result: InteractionResult
        files_snapshot: 文件快照数据

    Returns:
        新格式的 EvidenceBundle
    """
    from datetime import datetime
    from test_cases.black_box.evidence_models import FileRecord, WorkspaceSnapshot
    import hashlib
    from pathlib import Path

    # 获取最后一个 turn
    turn = result.turns[-1] if result.turns else None
    root = prepared.workspace_root

    # 构造文件记录
    files_added = []
    files_modified = []
    files_deleted = []

    before_snapshot = files_snapshot.get("before", {})
    after_snapshot = files_snapshot.get("after", {})

    # 识别新增、修改、删除的文件
    added_paths = set(after_snapshot.keys()) - set(before_snapshot.keys())
    deleted_paths = set(before_snapshot.keys()) - set(after_snapshot.keys())
    modified_paths = set()

    for path in set(before_snapshot.keys()) & set(after_snapshot.keys()):
        before_hash = before_snapshot[path].get("hash")
        after_hash = after_snapshot[path].get("hash")
        if before_hash != after_hash:
            modified_paths.add(path)

    # 读取文件内容
    def make_file_record(file_path: str, snapshot: dict) -> FileRecord:
        file_info = snapshot.get(file_path, {})
        full_path = root / file_path

        content = None
        encoding = None

        if full_path.is_file():
            try:
                content = full_path.read_text(encoding='utf-8')
                encoding = 'utf-8'
            except (UnicodeDecodeError, OSError):
                # 二进制文件或无法读取
                pass

        return FileRecord(
            path=file_path,
            content=content,
            content_hash=file_info.get("hash", ""),
            size_bytes=file_info.get("size", 0),
            modified_time=datetime.fromtimestamp(file_info.get("mtime", 0)) if file_info.get("mtime") else datetime.now(),
            encoding=encoding
        )

    for path in added_paths:
        files_added.append(make_file_record(path, after_snapshot))

    for path in modified_paths:
        files_modified.append(make_file_record(path, after_snapshot))

    files_deleted = list(deleted_paths)

    # 构造快照
    before_records = {path: make_file_record(path, before_snapshot) for path in before_snapshot}
    after_records = {path: make_file_record(path, after_snapshot) for path in after_snapshot}

    workspace_snapshot = WorkspaceSnapshot(
        before=before_records,
        after=after_records
    )

    # 获取 prompt
    prompt = ""
    if hasattr(prepared, 'spec') and hasattr(prepared.spec, 'steps') and prepared.spec.steps:
        prompt = prepared.spec.steps[0].prompt

    # 构造 EvidenceBundle
    evidence = EvidenceBundle(
        run_id=getattr(prepared, 'run_id', 'unknown'),
        case_id=prepared.spec.case_id if hasattr(prepared, 'spec') else 'unknown',
        timestamp=datetime.now(),
        prompt=prompt,
        agent_response=turn.response if turn else "",
        exit_code=getattr(result, 'exit_code', 0),
        stdout=getattr(turn, 'stdout', "") if turn else "",
        stderr=getattr(turn, 'stderr', "") if turn else "",
        execution_time_seconds=getattr(result, 'elapsed_seconds', 0),
        workspace_snapshot=workspace_snapshot,
        files_added=files_added,
        files_modified=files_modified,
        files_deleted=files_deleted,
        tool_calls=[],
        collector_ready=True,
        collection_complete=True,
        positive_control_ok=getattr(prepared, 'positive_control_ok', True)
    )

    return evidence
