"""Public entry points for generated black-box test wrappers."""

from test_cases.black_box.assertion import BlackBoxAssertion
from test_cases.black_box.environment import BlackBoxEnvironmentBuilder
from test_cases.black_box.evidence import BlackBoxEvidenceProjector
from test_cases.black_box.execution import BlackBoxCaseExecutor, register_case_handler
from test_cases.black_box.models import (AssertionRule, BlackBoxCaseSpec, BlackBoxEvidence,
                                         BlackBoxExecutionResult, PreparedBlackBoxEnvironment,
                                         PublicStepSpec, PublicTurnObservation, WorkspaceFileSpec)
from test_cases.black_box.runner import BlackBoxCaseRunner, run_black_box_case
from test_cases.black_box.specs import load_black_box_spec, load_black_box_specs

__all__ = ["AssertionRule", "BlackBoxAssertion", "BlackBoxCaseExecutor", "BlackBoxCaseRunner",
           "BlackBoxCaseSpec", "BlackBoxEnvironmentBuilder", "BlackBoxEvidence",
           "BlackBoxEvidenceProjector", "BlackBoxExecutionResult", "PreparedBlackBoxEnvironment",
           "PublicStepSpec", "PublicTurnObservation", "WorkspaceFileSpec", "load_black_box_spec",
           "load_black_box_specs", "register_case_handler", "run_black_box_case"]
