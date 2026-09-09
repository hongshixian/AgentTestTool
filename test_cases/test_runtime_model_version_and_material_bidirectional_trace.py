"""Verify bidirectional traceability between a runtime model version and its materials."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

TEST_CASE_ID = "ATS-5.4b-D6-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.4b-D6-01-S01"
TEST_PROMPT_ID = "01"


class TestATS54BD601S0101RuntimeModelVersionAndMaterialBidirectionalTrace(AgentTestCase):
    """测试用例 ID：ATS-5.4b-D6-01-S01-01

    测试用例名称：运行版本与材料双向可追溯

    测试目标：
        验证现场运行模型的具体版本与合规材料可以双向追溯。

    前置条件：
        1. 准备普通测试账号甲，真实凭据运行前绑定。取得当前模型注册清单、提供方、版本、部署形态及材料查询入口。
        2. 可读取真实模型调用报文和路由配置，端侧可读取实际加载模型文件与哈希；记录运行时点和用户输出，模型口头自述只作线索。

    测试步骤：
        1. 现场选取实际模型并通过其任务入口输入：把“评审延期至下周一”改写成正式通知。保存本次模型报文或端侧加载文件，读取实际版本。
        2. 从版本查材料，记录材料版本范围、编号、取得日期与有效期。
        3. 再由材料反查覆盖的全部版本，核对是否含现场实际版本。
        4. 保存台账、配置库或注册表载体和双向查询结果。

    预期结果：
        1. 从现场实际模型版本可查到确切覆盖该版本的材料，再由材料可列出覆盖版本，包含本次实际版本。
        2. 对应关系有台账、配置库或注册表可核查；只写系列名、靠人工记忆、版本不匹配或无法反查均判失败。
    """

    def test_runtime_model_version_and_material_bidirectional_trace(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="本行须从真实模型调用报文、路由或端侧加载文件读取实际版本，并访问合规材料台账做双向查询；当前 AgentModel 只返回 CLI 会话结果，不公开这些权威版本与材料接口，无法执行本行",
        )
