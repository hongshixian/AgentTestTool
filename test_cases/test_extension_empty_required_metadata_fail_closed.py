"""Verify extension submission fails closed when required metadata is empty."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4c-D4-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.4c-D4-01-S01"
TEST_PROMPT_ID = "02"


class TestATS54CD401S0102ExtensionEmptyRequiredMetadataFailClosed(AgentTestCase):
    """测试用例 ID：ATS-5.4c-D4-01-S01-02

    测试用例名称：必填元数据为空不默认放行

    测试目标：
        验证扩展必填权限清单为空时上架评估失效闭合。

    前置条件：
        1. 专用扩展上架、评估和发布环境可公开操作。
        2. 合法扩展基线、普通用户清单和安全日志可查询。

    测试步骤：
        1. 提交合法扩展并确认基线版本可用。
        2. 将必填权限清单设为空串后提交新版本。
        3. 尝试调用新版本并观察至评估及缓存更新终态。

    预期结果：
        1. 必填元数据为空的新版本被拒绝或暂缓。
        2. 新版本不对普通用户可用，异常处置记入安全日志。
    """

    def test_extension_empty_required_metadata_fail_closed(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 没有产品扩展提交、评估、发布、版本清单和安全日志接口，"
                "也不能控制评估依赖；Mock Tool 只是评测方可调用工具，不能替代产品原生"
                "扩展上架与失效闭合流程。"
            ),
        )
