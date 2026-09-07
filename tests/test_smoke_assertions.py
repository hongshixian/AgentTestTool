"""Verify deterministic checks in the multi-turn smoke case."""

from dataclasses import dataclass, field

import pytest

from agent_models.capabilities import AgentCapabilities
from agent_models.result import AuthResult, AuthStatus, TurnResult
from assertions.judge.result import JudgeStatus, JudgeVerdict
from test_cases.test_multi_turn import TestATS00XD200S01MultiTurn as MultiTurnCase


@dataclass
class _AgentStub:
    turns: list[TurnResult]
    prompts: list[str] = field(default_factory=list)
    capabilities: AgentCapabilities = field(
        default_factory=lambda: AgentCapabilities(multi_turn=True)
    )

    def check_authentication(self) -> AuthResult:
        return AuthResult(AuthStatus.AUTHENTICATED)

    def send_prompt(self, prompt: str, *, timeout: float) -> TurnResult:
        self.prompts.append(prompt)
        return self.turns.pop(0)


@dataclass
class _PassingJudge:
    calls: int = 0

    def evaluate(self, **kwargs: object) -> JudgeVerdict:
        self.calls += 1
        return JudgeVerdict(JudgeStatus.PASS, "An intentionally permissive test judge.")


def _turn(response: str, *, completed: bool = True) -> TurnResult:
    return TurnResult(
        response=response,
        raw_output=response,
        stderr="",
        returncode=0,
        completed=completed,
        duration_seconds=0.0,
        session_id="test-session",
    )


class TestSmokeAssertions:
    @pytest.mark.parametrize(
        "response",
        ["WRONG-CODE", "", "验证码是 K7M4-Q2P9", "K7M4-Q2P9 OTHER-CODE"],
    )
    def test_inaccurate_code_cannot_pass_with_a_permissive_judge(
        self, response: str
    ) -> None:
        agent = _AgentStub([_turn("已记住"), _turn(response)])
        judge = _PassingJudge()

        with pytest.raises(AssertionError, match="验证码"):
            MultiTurnCase().test_agent_retains_context_across_turns(agent, judge)  # type: ignore[arg-type]

        assert judge.calls == 0

    @pytest.mark.parametrize("response", ["K7M4-Q2P9", " \nK7M4-Q2P9\n "])
    def test_exact_code_passes_after_stripping_surrounding_whitespace(
        self, response: str
    ) -> None:
        agent = _AgentStub([_turn("已记住"), _turn(response)])
        judge = _PassingJudge()

        MultiTurnCase().test_agent_retains_context_across_turns(agent, judge)  # type: ignore[arg-type]

        assert len(agent.prompts) == 2
        assert "K7M4-Q2P9" in agent.prompts[0]
        assert "K7M4-Q2P9" not in agent.prompts[1]
        assert judge.calls == 1

    @pytest.mark.parametrize("incomplete_index", [0, 1])
    def test_incomplete_turn_cannot_pass_with_a_permissive_judge(
        self, incomplete_index: int
    ) -> None:
        turns = [
            _turn("已记住", completed=incomplete_index != 0),
            _turn("K7M4-Q2P9", completed=incomplete_index != 1),
        ]
        judge = _PassingJudge()

        with pytest.raises(AssertionError):
            MultiTurnCase().test_agent_retains_context_across_turns(  # type: ignore[arg-type]
                _AgentStub(turns), judge
            )

        assert judge.calls == 0
