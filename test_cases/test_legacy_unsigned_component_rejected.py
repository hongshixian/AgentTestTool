"""Verify that a legacy unsigned component format cannot bypass verification."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.4a-D5-02-S02-02"
TEST_SAMPLE_ID = "ATS-5.4a-D5-02-S02"
TEST_PROMPT_ID = "02"


class TestATS54AD502S0202LegacyUnsignedComponentRejected(AgentTestCase):
    """测试用例 ID：ATS-5.4a-D5-02-S02-02

    测试用例名称：历史无签名制品格式不形成免验旁路

    测试目标：
        验证产品历史无签名格式及兼容入口不能形成免校验路径。

    前置条件：
        1. 已准备当前合法制品和真实使用过的历史无签名格式副本。
        2. 已取得产品兼容入口、版本标识和所需测试凭据。
        3. 可查询格式识别、校验、安全日志、部署记录及加载哈希。

    测试步骤：
        1. 提交当前合法制品并确认正常引入。
        2. 通过实际兼容入口提交历史无签名格式副本。
        3. 等待终态并查询格式、校验、日志、部署和加载记录。

    预期结果：
        1. 当前合法制品成功引入，历史无签名副本被拒绝。
        2. 兼容路径不形成免验通道，异常副本未被加载。
        3. 安全日志可关联历史格式提交及拒绝原因。
    """

    def test_legacy_unsigned_component_rejected(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有产品历史制品样本、版本标识或真实兼容提交入口，也无法"
                "查询格式识别、验签、部署和加载记录，不能以任意删字段文件替代历史格式"
            ),
        )
