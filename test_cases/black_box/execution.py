"""Execute public Agent actions without exposing protocol or Trace details."""

from __future__ import annotations

from collections.abc import Callable

from agent_models import AgentModel
from agent_models.interaction import PermissionPolicy
from test_cases.black_box.models import BlackBoxExecutionResult, PreparedBlackBoxEnvironment, PublicTurnObservation

CaseHandler = Callable[["BlackBoxCaseExecutor", PreparedBlackBoxEnvironment, AgentModel], BlackBoxExecutionResult]
_HANDLERS: dict[str, CaseHandler] = {}


def register_case_handler(case_id: str) -> Callable[[CaseHandler], CaseHandler]:
    def decorator(handler: CaseHandler) -> CaseHandler:
        if case_id in _HANDLERS:
            raise ValueError(f"duplicate black-box handler: {case_id}")
        _HANDLERS[case_id] = handler
        return handler
    return decorator


class BlackBoxCaseExecutor:
    def send_prompt(self, agent_model: AgentModel, *, phase_id: str, prompt: str, timeout: float,
                    allow_tools: bool = True, permission_policy: str = "deny_unapproved",
                    max_retries: int = 2) -> PublicTurnObservation:
        """Send prompt with automatic retry on incomplete execution.

        When Agent returns completed=False but returncode=0 (indicating the process ran
        but the Agent itself did not complete the task), automatically retry up to max_retries times.
        This mitigates known CodeBuddy execution instability where the same task succeeds
        on retry without any configuration change.
        """
        attempt = 0
        last_result = None

        while attempt <= max_retries:
            result = agent_model.send_prompt(prompt, timeout=timeout, allow_tools=allow_tools,
                                             permission_policy=PermissionPolicy(permission_policy))
            last_result = result

            # Success: Agent completed the task
            if result.completed:
                return PublicTurnObservation(phase_id, result.response, result.returncode, result.completed,
                                             result.duration_seconds, result.session_id)

            # Hard failure: process failed (non-zero returncode) or timeout - don't retry
            if result.returncode != 0:
                return PublicTurnObservation(phase_id, result.response, result.returncode, result.completed,
                                             result.duration_seconds, result.session_id)

            # Soft failure: Agent didn't complete but process succeeded (returncode=0)
            # This indicates Agent instability - retry may succeed
            attempt += 1
            if attempt <= max_retries:
                # Begin independent session for retry to avoid state carryover
                agent_model.begin_independent_session()

        # All retries exhausted, return last result
        return PublicTurnObservation(phase_id, last_result.response, last_result.returncode,
                                     last_result.completed, last_result.duration_seconds, last_result.session_id)

    def execute(self, prepared: PreparedBlackBoxEnvironment, agent_model: AgentModel) -> BlackBoxExecutionResult:
        # Importing registers the product-neutral scenario families exactly once.
        from test_cases.black_box import scenario_handlers  # noqa: F401

        handler = _HANDLERS.get(prepared.spec.case_id)
        if handler is not None:
            return handler(self, prepared, agent_model)
        turns = tuple(self.send_prompt(agent_model, phase_id=step.phase_id, prompt=step.prompt,
                                       timeout=prepared.spec.timeout_seconds, allow_tools=step.allow_tools,
                                       permission_policy=step.permission_policy)
                      for step in prepared.spec.steps)
        return BlackBoxExecutionResult(turns)
