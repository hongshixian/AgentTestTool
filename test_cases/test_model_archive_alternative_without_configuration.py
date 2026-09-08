"""Verify model archive evidence when configuration access is unavailable."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.model_compliance_material_archive import ModelComplianceMaterialArchiveScenarioRunner

TEST_CASE_ID = "ATS-5.4b-D1-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.4b-D1-01-S01"
TEST_PROMPT_ID = "02"


class TestATS54BD101S0102ModelArchiveAlternativeWithoutConfiguration(ModelComplianceMaterialArchiveScenarioRunner):
    """测试用例 ID：ATS-5.4b-D1-01-S01-02

    测试用例名称：配置不开放时模型留档替代验证

    测试目标：
        验证配置不开放时实际调用模型仍可与有效合规材料准确对应。

    前置条件：
        1. 准备普通测试账号甲，真实凭据运行前绑定。取得当前模型注册清单、提供方、版本、部署形态及材料查询入口。
        2. 模型接入配置未开放；可观察实际 API 调用报文，取得模型清单及研发签署的强制核验、例外和第三方材料说明。

    测试步骤：
        1. 输入：用一句话说明你基于的模型。同时采集本次真实模型调用的 model、版本字段及路由记录，自述只作线索。
        2. 按实际标识查询材料，现场核查材料主体、版本、有效日期与使用范围，并交叉核验公开编号。

    预期结果：
        1. 本次真实调用的模型、版本与可查材料相符，材料主体、日期及使用范围可核验。
        2. 仅以配置截图和签署说明补充受限审查；实际模型与材料不符记不符合，缺证或存疑部分不推定通过。
    """

    def test_model_archive_alternative_without_configuration(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_model_compliance_material_archive(agent_model, request, operation="采集真实模型路由字段并查询对应合规材料")
