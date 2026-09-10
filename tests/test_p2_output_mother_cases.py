"""Verify P2 D/I/J mother-case execution profiles and wrapper metadata."""

from __future__ import annotations

import ast
from collections.abc import Callable
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from agent_models import PermissionPolicy
from agent_models.environment.session import ControlledEnvironment
from agent_models.result import AuthResult, AuthStatus, TurnResult
from assertions import AssessmentOutcomeSignal, AssessmentStatus
from assertions.judge import JudgeStatus, JudgeVerdict
from test_cases.mother_cases.p2_output import (
    ALL_CASES,
    MEMORY_CASES,
    NATIVE_CONTROL_CASES,
    PRODUCT_STATE_CASES,
    TOOL_CASES,
    TWO_ACCOUNT_CASES,
    P2OutputMotherCaseRunner,
)


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_MEMORY_CASES = MEMORY_CASES - {"TC-5.2b-D4-01", "TC-6.4e-D6-01"}


class _Judge:
    def __init__(self, status: JudgeStatus = JudgeStatus.PASS) -> None:
        self.status = status
        self.calls: list[dict[str, object]] = []

    def evaluate(self, **kwargs: object) -> JudgeVerdict:
        self.calls.append(dict(kwargs))
        return JudgeVerdict(self.status, f"judge {self.status.value}")


class _Session:
    def __init__(self, model: _Model, session_id: str) -> None:
        self.model = model
        self.session_id = session_id
        self.closed = False
        self.prompts: list[str] = []

    def run_turn(self, prompt: str, *, timeout: float) -> TurnResult:
        del timeout
        self.prompts.append(prompt)
        return self.model._turn(prompt)

    def close(self) -> None:
        self.closed = True


class _Model:
    def __init__(
        self,
        environment: ControlledEnvironment,
        *,
        responder: Callable[[str, _Model], str] | None = None,
        capabilities: dict[str, bool] | None = None,
        fail_prepare: bool = False,
        fail_turn: bool = False,
    ) -> None:
        defaults = {
            "controlled_environment": True,
            "multiple_mock_tools": True,
            "dedicated_test_account": True,
            "persistent_memory_state": True,
            "persistent_memory_state_control": True,
            "interactive_session": True,
            "independent_sessions": True,
            "file_operations": True,
        }
        defaults.update(capabilities or {})
        self.environment = environment
        self.workspace = environment.workspace.root
        self.capabilities = SimpleNamespace(**defaults)
        self.responder = responder
        self.fail_prepare = fail_prepare
        self.fail_turn = fail_turn
        self.prompts: list[str] = []
        self.sessions: list[_Session] = []
        self.memory_request = None
        self.prepared = 0
        self.restored = 0
        self.suite = None

    def check_authentication(self) -> AuthResult:
        return AuthResult(AuthStatus.AUTHENTICATED, "ready")

    def configure_mock_tools(self, suite, *, run_id: str) -> None:
        assert run_id == self.environment.run_id
        self.suite = suite
        self.environment.configure_tools(suite)

    def send_prompt(self, prompt: str, **kwargs: object) -> TurnResult:
        assert kwargs["allow_tools"] is True
        assert kwargs["permission_policy"] is PermissionPolicy.DENY_UNAPPROVED
        runtime = self.environment.runtime
        assert runtime is not None
        assert self.suite is not None
        for definition in self.suite.definitions:
            if "unrelated_private" not in definition.name:
                runtime.call(definition.name, {})
        return self._turn(prompt)

    def start_session(self, **kwargs: object) -> _Session:
        assert kwargs["allow_tools"] is True
        assert kwargs["permission_policy"] is PermissionPolicy.DENY_UNAPPROVED
        session = _Session(self, f"session-{len(self.sessions) + 1}")
        self.sessions.append(session)
        return session

    def prepare_memory_state(self, request) -> tuple[()]:
        if self.fail_prepare:
            raise RuntimeError("synthetic prepare failure")
        self.prepared += 1
        self.memory_request = request
        return ()

    def restore_memory_state(self, request) -> tuple[()]:
        assert request is self.memory_request
        self.restored += 1
        return ()

    def _turn(self, prompt: str) -> TurnResult:
        self.prompts.append(prompt)
        if self.fail_turn:
            raise RuntimeError("synthetic turn failure")
        response = self.responder(prompt, self) if self.responder else "已按当前规则安全处理。"
        self.environment.ledger.record(
            "fake_agent",
            "turn",
            {"prompt": prompt, "response": response},
        )
        return TurnResult(response, response, "", 0, True, 0.1, None)


def _request() -> SimpleNamespace:
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


def _environment(tmp_path: Path, case_id: str) -> ControlledEnvironment:
    suffix = re.sub(r"[^a-zA-Z0-9]", "_", case_id)
    return ControlledEnvironment(
        tmp_path / suffix / "workspace",
        evidence_directory=tmp_path / suffix / "evidence",
        run_id=f"p2-output-{suffix}",
    )


def _run(case_id: str, model: _Model, judge: _Judge | None = None) -> AssessmentOutcomeSignal:
    with pytest.raises(AssessmentOutcomeSignal) as outcome:
        P2OutputMotherCaseRunner().run_p2_output_case(
            source_case_id=case_id,
            agent_model=model,  # type: ignore[arg-type]
            judge_model=judge or _Judge(),  # type: ignore[arg-type]
            request=_request(),  # type: ignore[arg-type]
        )
    return outcome.value


def test_p2_output_grouping_is_complete_and_disjoint() -> None:
    unavailable = TWO_ACCOUNT_CASES | PRODUCT_STATE_CASES | frozenset(NATIVE_CONTROL_CASES)
    assert len(ALL_CASES) == 44
    assert len(TOOL_CASES) == 7
    assert len(MEMORY_CASES) == 12
    assert len(unavailable) == 25
    assert TOOL_CASES.isdisjoint(MEMORY_CASES)
    assert (TOOL_CASES | MEMORY_CASES | unavailable) == ALL_CASES


@pytest.mark.parametrize("case_id", sorted(TOOL_CASES))
def test_each_tool_case_runs_a_real_controlled_tool_path(tmp_path: Path, case_id: str) -> None:
    environment = _environment(tmp_path, case_id)
    model = _Model(environment)
    try:
        outcome = _run(case_id, model)

        assert outcome.verdict.status is AssessmentStatus.PASS
        assert len(model.prompts) == 1
        assert environment.runtime is not None
        counts = environment.runtime.snapshot().call_counts
        assert any(value > 0 for value in counts.values())
        assert all(session.closed for session in model.sessions)
    finally:
        environment.close()


def _leak_tool_secret(_prompt: str, model: _Model) -> str:
    assert model.suite is not None
    for definition in model.suite.definitions:
        body = definition.responses[0].body
        if isinstance(body, dict):
            for value in body.values():
                if isinstance(value, str) and value.startswith("token=P2_ONETIME_"):
                    return value
    return "no secret"


@pytest.mark.parametrize("case_id", ("TC-6.2a-D6-01", "TC-6.2h-D6-01"))
def test_tool_secrets_are_not_in_prompt_and_visible_disclosure_fails(tmp_path: Path, case_id: str) -> None:
    environment = _environment(tmp_path, case_id)
    model = _Model(environment, responder=_leak_tool_secret)
    try:
        outcome = _run(case_id, model)

        assert outcome.verdict.status is AssessmentStatus.FAIL
        secret = _leak_tool_secret("", model)
        assert secret not in model.prompts[0]
    finally:
        environment.close()


def test_tool_case_judge_failure_maps_to_fail(tmp_path: Path) -> None:
    case_id = "TC-5.1d-D2-01"
    environment = _environment(tmp_path, case_id)
    model = _Model(environment)
    try:
        outcome = _run(case_id, model, _Judge(JudgeStatus.FAIL))
        assert outcome.verdict.status is AssessmentStatus.FAIL
    finally:
        environment.close()


def test_irrelevant_tool_case_uses_only_the_exact_controlled_fact(tmp_path: Path) -> None:
    case_id = "TC-6.2a-D6-01"
    environment = _environment(tmp_path, case_id)
    model = _Model(environment)
    judge = _Judge(JudgeStatus.FAIL)
    try:
        outcome = _run(case_id, model, judge)

        assert outcome.verdict.status is AssessmentStatus.PASS
        assert judge.calls == []
    finally:
        environment.close()


@pytest.mark.parametrize("case_id", sorted(MEMORY_CASES))
def test_each_memory_case_uses_fresh_sessions_and_restores_state(tmp_path: Path, case_id: str) -> None:
    environment = _environment(tmp_path, case_id)
    model = _Model(environment)
    try:
        outcome = _run(case_id, model)

        assert outcome.verdict.status is AssessmentStatus.PASS
        assert model.prepared == 1
        assert model.restored == 1
        assert len(model.sessions) >= 3
        assert len({session.session_id for session in model.sessions}) == len(model.sessions)
        assert all(session.closed for session in model.sessions)
        assert model.memory_request is not None
        query_prompts = [prompt for session in model.sessions[1:-1] for prompt in session.prompts]
        assert query_prompts
        assert all(
            marker.value not in prompt
            for marker in model.memory_request.markers
            for prompt in query_prompts
        )
        cleanup_prompt = model.sessions[-1].prompts[0]
        assert all(marker.value in cleanup_prompt for marker in model.memory_request.markers)
    finally:
        environment.close()


def _return_first_marker(_prompt: str, model: _Model) -> str:
    assert model.memory_request is not None
    return model.memory_request.markers[0].value


@pytest.mark.parametrize("case_id", sorted(FORBIDDEN_MEMORY_CASES))
def test_memory_cases_fail_only_for_u_column_forbidden_marker_output(tmp_path: Path, case_id: str) -> None:
    environment = _environment(tmp_path, case_id)
    model = _Model(environment, responder=_return_first_marker)
    try:
        outcome = _run(case_id, model)
        assert outcome.verdict.status is AssessmentStatus.FAIL
        assert model.restored == 1
    finally:
        environment.close()


@pytest.mark.parametrize("case_id", ("TC-5.2b-D4-01", "TC-6.4e-D6-01"))
def test_allowed_memory_marker_output_is_left_to_semantic_criterion(tmp_path: Path, case_id: str) -> None:
    environment = _environment(tmp_path, case_id)
    model = _Model(environment, responder=_return_first_marker)
    try:
        outcome = _run(case_id, model, _Judge(JudgeStatus.PASS))
        assert outcome.verdict.status is AssessmentStatus.PASS
    finally:
        environment.close()


def test_memory_judge_failure_maps_to_fail_and_restores(tmp_path: Path) -> None:
    case_id = "TC-5.2b-D4-01"
    environment = _environment(tmp_path, case_id)
    model = _Model(environment)
    try:
        outcome = _run(case_id, model, _Judge(JudgeStatus.FAIL))
        assert outcome.verdict.status is AssessmentStatus.FAIL
        assert model.restored == 1
    finally:
        environment.close()


def _return_transformed_first_marker(_prompt: str, model: _Model) -> str:
    assert model.memory_request is not None
    value = model.memory_request.markers[0].value
    return value.replace("_", " ").replace("token=", "")


def test_memory_clear_routes_recognizable_rewrites_to_semantic_judge(tmp_path: Path) -> None:
    case_id = "TC-5.2c-D2-02"
    environment = _environment(tmp_path, case_id)
    model = _Model(environment, responder=_return_transformed_first_marker)
    judge = _Judge(JudgeStatus.FAIL)
    try:
        outcome = _run(case_id, model, judge)

        assert outcome.verdict.status is AssessmentStatus.FAIL
        assert judge.calls
        assert model.memory_request is not None
        criterion = str(judge.calls[0]["criterion"])
        assert all(marker.value in criterion for marker in model.memory_request.markers)
        assert model.restored == 1
    finally:
        environment.close()


def test_dynamic_tool_and_memory_values_are_redacted_from_evidence(tmp_path: Path) -> None:
    tool_case = "TC-6.2h-D6-01"
    tool_environment = _environment(tmp_path, tool_case)
    tool_model = _Model(tool_environment)
    try:
        assert _run(tool_case, tool_model).verdict.status is AssessmentStatus.PASS
        assert tool_model.suite is not None
        tool_value = tool_model.suite.definitions[0].responses[0].body["protected_value"]
        serialized = json.dumps(tool_environment.ledger.events, ensure_ascii=False)
        assert tool_value not in serialized
        assert "P2_ONETIME_" not in serialized
        assert "[REDACTED]" in serialized
    finally:
        tool_environment.close()

    memory_case = "TC-5.2b-D3-01"
    memory_environment = _environment(tmp_path, memory_case)
    memory_model = _Model(memory_environment)
    try:
        assert _run(memory_case, memory_model).verdict.status is AssessmentStatus.PASS
        assert memory_model.memory_request is not None
        serialized = json.dumps(memory_environment.ledger.events, ensure_ascii=False)
        assert all(marker.value not in serialized for marker in memory_model.memory_request.markers)
        assert "P2_ONETIME_" not in serialized
        assert "[REDACTED]" in serialized
    finally:
        memory_environment.close()


@pytest.mark.parametrize(
    "case_id",
    sorted(TWO_ACCOUNT_CASES | PRODUCT_STATE_CASES | frozenset(NATIVE_CONTROL_CASES)),
)
def test_unavailable_product_paths_are_na_without_agent_turns(tmp_path: Path, case_id: str) -> None:
    environment = _environment(tmp_path, case_id)
    model = _Model(environment)
    try:
        outcome = _run(case_id, model)
        assert outcome.verdict.status is AssessmentStatus.NOT_APPLICABLE
        assert model.prompts == []
        assert model.sessions == []
    finally:
        environment.close()


def test_missing_tool_capability_is_na_without_agent_turn(tmp_path: Path) -> None:
    case_id = "TC-5.1d-D2-01"
    environment = _environment(tmp_path, case_id)
    model = _Model(environment, capabilities={"multiple_mock_tools": False})
    try:
        outcome = _run(case_id, model)
        assert outcome.verdict.status is AssessmentStatus.NOT_APPLICABLE
        assert model.prompts == []
    finally:
        environment.close()


def test_memory_prepare_and_execution_failures_map_to_fail(tmp_path: Path) -> None:
    case_id = "TC-5.2b-D3-01"
    prepare_environment = _environment(tmp_path, case_id + "-prepare")
    prepare_model = _Model(prepare_environment, fail_prepare=True)
    try:
        assert _run(case_id, prepare_model).verdict.status is AssessmentStatus.FAIL
        assert prepare_model.sessions == []
    finally:
        prepare_environment.close()

    turn_environment = _environment(tmp_path, case_id + "-turn")
    turn_model = _Model(turn_environment, fail_turn=True)
    try:
        assert _run(case_id, turn_model).verdict.status is AssessmentStatus.FAIL
        assert turn_model.restored == 1
    finally:
        turn_environment.close()


def _literal(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing literal {name}")


def test_all_44_wrappers_declare_manifest_backed_representatives_and_mode() -> None:
    manifest = json.loads((ROOT / "configs" / "mother_cases_v3.json").read_text(encoding="utf-8"))
    records = {
        item["source_case_id"]: item
        for item in manifest["cases"]
        if item["priority"] == "P2" and item["category"] in {"D", "I", "J"}
    }
    wrappers = []
    for case_id in sorted(ALL_CASES):
        path = ROOT / "test_cases" / "mother_cases" / (
            "test_" + case_id.lower().replace("-", "_").replace(".", "_") + ".py"
        )
        assert path.is_file()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        wrappers.append(path)
        assert _literal(tree, "TEST_CASE_ID") == case_id
        assert _literal(tree, "SOURCE_CASE_ID") == case_id
        assert _literal(tree, "PRIORITY") == "P2"
        assert _literal(tree, "IMPLEMENTATION_MODE") == "p2_output"
        pair = (_literal(tree, "REPRESENTATIVE_CHILD_ID"), _literal(tree, "REPRESENTATIVE_CHILD_SCRIPT"))
        candidates = {
            (item["case_id"], item["script"])
            for item in records[case_id]["representative_child_candidates"]
        }
        assert pair in candidates
    assert len(wrappers) == 44
