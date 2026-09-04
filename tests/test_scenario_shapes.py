"""Verify implemented ATS samples preserve their source scenario shapes."""

from test_cases.security import SecurityIdentitySettings
from test_cases import test_cross_identity_replay as s01
from test_cases import test_instance_id_boundaries as s02
from test_cases import test_local_instance_state_tampering as s03
from test_cases import test_natural_language_identity_override as s04
from test_cases import test_tool_result_identity_injection as s05
from test_cases.base import AgentTestCase


class TestScenarioShapes:
    def test_sample_ids_and_repeat_counts(self) -> None:
        modules = (s01, s02, s03, s04, s05)

        assert [module.SAMPLE_ID for module in modules] == [
            "ATS-5.1b-D5-02-S01",
            "ATS-5.1b-D5-02-S02",
            "ATS-5.1b-D5-02-S03",
            "ATS-5.1b-D5-02-S04",
            "ATS-5.1b-D5-02-S05",
        ]
        assert all(module.REPEAT_COUNT == 3 for module in modules)

    def test_formal_sample_classes_follow_shared_case_contract(self) -> None:
        classes = (
            s01.TestATS51BD502S01CrossIdentityReplay,
            s02.TestATS51BD502S02InstanceIdBoundaries,
            s03.TestATS51BD502S03LocalInstanceStateTampering,
            s04.TestATS51BD502S04NaturalLanguageIdentityOverride,
            s05.TestATS51BD502S05ToolResultIdentityInjection,
        )

        for index, case_class in enumerate(classes, start=1):
            assert issubclass(case_class, AgentTestCase)
            assert f"ATS-5.1b-D5-02-S{index:02d}" in (case_class.__doc__ or "")

    def test_prompt_ids_and_turn_counts(self) -> None:
        settings = SecurityIdentitySettings("token", "a-user", "a-instance", "b-user", "b-instance")
        s01_variants = [
            s01._variant(name, settings, "destroyed-instance")
            for name in ("cross_01", "cross_02", "cross_03")
        ]

        assert [(item.prompt_id, len(item.turns)) for item in s01_variants] == [
            ("CROSS-ID-01", 2),
            ("CROSS-ID-02", 1),
            ("CROSS-ID-03", 2),
        ]
        assert [item.prompt_id for item in s02.VARIANTS] == [
            "BOUNDARY-01",
            "BOUNDARY-02",
            "BOUNDARY-03",
        ]
        assert [item.prompt_id for item in s03.VARIANTS] == [
            "LOCAL-STATE-01",
            "LOCAL-STATE-02",
        ]
        assert [item.prompt_id for item in s04.PROMPT_VARIANTS] == [
            "LANGUAGE-01",
            "LANGUAGE-02",
            "LANGUAGE-03",
        ]
        assert [item.prompt_id for item in s05.VARIANTS] == [
            "TOOL-INJECTION-01",
            "TOOL-INJECTION-02",
        ]

    def test_judge_criterion_counts(self) -> None:
        settings = SecurityIdentitySettings("token", "a-user", "a-instance", "b-user", "b-instance")
        s01_variants = [
            s01._variant(name, settings, "destroyed-instance")
            for name in ("cross_01", "cross_02", "cross_03")
        ]

        assert [(len(s01._pass_criteria(item)), len(s01._fail_criteria(item))) for item in s01_variants] == [
            (6, 4),
            (7, 5),
            (6, 4),
        ]
        for prompt_id in ("BOUNDARY-01", "BOUNDARY-02", "BOUNDARY-03"):
            assert (len(s02._pass_criteria(prompt_id)), len(s02._fail_criteria(prompt_id))) == (6, 4)
        for prompt_id in ("LOCAL-STATE-01", "LOCAL-STATE-02"):
            assert (len(s03._pass_criteria(prompt_id)), len(s03._fail_criteria(prompt_id))) == (6, 4)
        for prompt_id in ("LANGUAGE-01", "LANGUAGE-02", "LANGUAGE-03"):
            assert (len(s04._pass_criteria(prompt_id)), len(s04._fail_criteria(prompt_id))) == (6, 4)
        for prompt_id in ("TOOL-INJECTION-01", "TOOL-INJECTION-02"):
            assert (len(s05._pass_criteria(prompt_id)), len(s05._fail_criteria(prompt_id))) == (6, 4)
