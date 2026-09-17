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
                    allow_tools: bool = True, permission_policy: str = "deny_unapproved") -> PublicTurnObservation:
        result = agent_model.send_prompt(prompt, timeout=timeout, allow_tools=allow_tools,
                                         permission_policy=PermissionPolicy(permission_policy))
        return PublicTurnObservation(phase_id, result.response, result.returncode, result.completed,
                                     result.duration_seconds, result.session_id)

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
