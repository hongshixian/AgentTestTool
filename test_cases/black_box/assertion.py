"""Deterministic assertions over the narrow black-box evidence projection."""

from typing import Optional

from agent_models.evidence import JsonValue
from assertions.judge.model import JudgeConfig, OpenAICompatibleJudge
from assertions.outcome import AssessmentStatus, AssessmentVerdict, assessment_verdict
from test_cases.black_box.models import AssertionRule, BlackBoxCaseSpec, BlackBoxEvidence
from test_cases.black_box.evidence_models import JudgeCriterion


def _compare(actual: JsonValue, rule: AssertionRule) -> bool:
    expected = rule.expected
    operations = {"eq": lambda: actual == expected, "ne": lambda: actual != expected,
                  "lt": lambda: actual < expected, "le": lambda: actual <= expected,
                  "gt": lambda: actual > expected, "ge": lambda: actual >= expected,
                  "contains": lambda: expected in actual, "not_contains": lambda: expected not in actual}
    try:
        return bool(operations[rule.operator]())
    except (TypeError, KeyError):
        return False


class BlackBoxAssertion:
    """黑盒断言评估

    设计原则：
    - 优先使用 Judge 评审（如果 spec 有 judge_criterion）
    - Fallback 到旧的确定性断言（用于向后兼容）
    """

    def __init__(self, judge_model: Optional[OpenAICompatibleJudge] = None):
        self.judge_model = judge_model

    def evaluate(self, spec: BlackBoxCaseSpec, evidence: BlackBoxEvidence) -> AssessmentVerdict:
        # 检查证据完整性（确定性检查）
        if not evidence.control.collector_ready or not evidence.control.collection_complete:
            return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, "黑盒公开证据采集未完整闭合",
                                     ("完整的 PUBLIC/FILE/CONTROL 证据",))
        if not evidence.control.positive_control_ok:
            return assessment_verdict(
                AssessmentStatus.FAIL,
                reason="黑盒正对照未通过公开完成状态检查",
            )

        # 如果有 judge_criterion，使用 Judge 评审
        if spec.judge_criterion is not None:
            return self._evaluate_with_judge(spec, evidence)

        # Fallback：使用旧的确定性断言（向后兼容）
        return self._evaluate_with_rules(spec, evidence)

    def _evaluate_with_judge(self, spec: BlackBoxCaseSpec, evidence: BlackBoxEvidence) -> AssessmentVerdict:
        """使用 Judge 进行语义评审"""
        from test_cases.black_box.judge_assessment import JudgeAssessment, create_evidence_bundle_from_legacy

        # 确保有 Judge 模型
        if self.judge_model is None:
            try:
                config = JudgeConfig.from_environment()
                self.judge_model = OpenAICompatibleJudge(config)
            except Exception as e:
                return assessment_verdict(
                    AssessmentStatus.FAIL,
                    reason=f"{spec.case_id} Judge 模型初始化失败：{str(e)}"
                )

        # 转换为新的证据格式
        try:
            # 构造文件快照数据
            files_snapshot = {
                "before": {
                    entry.path: {
                        "hash": entry.sha256,
                        "size": 0,  # 旧格式没有大小信息
                        "mtime": 0   # 旧格式没有时间信息
                    }
                    for entry in evidence.files.before.entries
                    if not entry.is_directory
                },
                "after": {
                    entry.path: {
                        "hash": entry.sha256,
                        "size": 0,
                        "mtime": 0
                    }
                    for entry in evidence.files.after.entries
                    if not entry.is_directory
                }
            }

            # 创建一个假的 prepared 对象
            class FakePrepared:
                def __init__(self, spec, workspace_root):
                    self.spec = spec
                    self.workspace_root = workspace_root
                    self.run_id = evidence.control.run_id
                    self.positive_control_ok = evidence.control.positive_control_ok

            # 创建一个假的 result 对象
            class FakeResult:
                def __init__(self, turns, elapsed_seconds):
                    self.turns = turns
                    self.elapsed_seconds = elapsed_seconds

            # 从 evidence.files.after 推断工作区根目录
            # 这是一个简化假设，实际应该从环境中获取
            from pathlib import Path
            workspace_root = Path.cwd() / ".temp_workspace"  # 占位符

            prepared = FakePrepared(spec, workspace_root)
            result = FakeResult(
                turns=list(evidence.public.turns),
                elapsed_seconds=sum(t.duration_seconds for t in evidence.public.turns)
            )

            evidence_bundle = create_evidence_bundle_from_legacy(
                prepared,
                result,
                files_snapshot
            )
        except Exception as e:
            return assessment_verdict(
                AssessmentStatus.FAIL,
                reason=f"{spec.case_id} 证据转换失败：{str(e)}"
            )

        # 转换 judge_criterion 格式
        criterion = JudgeCriterion(
            case_id=spec.judge_criterion.case_id,
            title=spec.judge_criterion.title,
            description=spec.judge_criterion.description,
            pass_criteria=spec.judge_criterion.pass_criteria,
            fail_criteria=spec.judge_criterion.fail_criteria,
            required_evidence=list(spec.judge_criterion.required_evidence),
            checkpoints=list(spec.judge_criterion.checkpoints) if spec.judge_criterion.checkpoints else None
        )

        # 调用 Judge 评审
        assessment = JudgeAssessment(self.judge_model)
        return assessment.evaluate(evidence_bundle, criterion)

    def _evaluate_with_rules(self, spec: BlackBoxCaseSpec, evidence: BlackBoxEvidence) -> AssessmentVerdict:
        """使用旧的确定性断言规则（向后兼容）"""
        metrics = dict(evidence.metrics)
        metrics.setdefault("Completed_Count", sum(turn.completed for turn in evidence.public.turns))
        metrics.setdefault("Nonzero_Returncode_Count", sum(turn.returncode != 0 for turn in evidence.public.turns))
        metrics.setdefault("Workspace_Change_Count", len(evidence.files.added) + len(evidence.files.modified)
                           + len(evidence.files.deleted))
        metrics.setdefault("Positive_Output_Marker_Hits",
                           evidence.public.output_text.count(spec.public_marker) if spec.public_marker else 0)
        metrics.setdefault("Forbidden_Marker_Hits",
                           evidence.public.output_text.count(spec.marker) if spec.marker else 0)

        failures = [f"{rule.metric}={metrics.get(rule.metric)!r} 不满足 {rule.operator} {rule.expected!r}"
                    for rule in spec.assertion_rules
                    if rule.metric not in metrics or not _compare(metrics.get(rule.metric), rule)]
        if failures:
            return assessment_verdict(AssessmentStatus.FAIL, reason="；".join(failures))
        if not spec.assertion_rules:
            return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, "用例尚未声明可计算的黑盒断言规则",
                                     ("assertion_rules",))
        return assessment_verdict(AssessmentStatus.PASS,
                                  reason=f"{spec.case_id} 的 PUBLIC/FILE/CONTROL 黑盒断言全部满足")
