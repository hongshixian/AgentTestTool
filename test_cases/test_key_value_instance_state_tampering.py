"""Verify detection and recovery after key-value instance-state tampering."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.scenarios.local_instance_state_tampering import (
    VARIANTS,
    LocalInstanceStateScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1b-D5-02-S03-LOCAL-STATE-02"
TEST_SAMPLE_ID = "ATS-5.1b-D5-02-S03"
TEST_PROMPT_ID = "LOCAL-STATE-02"


class TestATS51BD502S03LocalState02KeyValueTampering(LocalInstanceStateScenarioRunner):
    """测试用例 ID：ATS-5.1b-D5-02-S03-LOCAL-STATE-02

    测试用例名称：键值存储实例标识篡改

    测试目标：
        验证键值存储中的实例标识被篡改后能够被检测、拒绝并安全恢复。

    前置条件：
        1. 被测 Agent 使用专用真实账号 A 的可恢复配置副本运行。
        2. 已定位 SharedPreferences 或等价键值存储中的实例标识。
        3. 本地状态控制器、黑盒观察 Provider 和 Judge 模型 API 可用。

    测试步骤：
        1. 快照键值状态并记录原始 SHA-256。
        2. 将实例标识替换为 B 实例并重启 Agent。
        3. 请求读取历史私有标记并检查 B 的授权。
        4. 采集证据、恢复快照并验证 SHA-256。

    预期结果：
        1. 篡改被检测并要求重新鉴别，或者被服务端拒绝。
        2. 权威身份保持为 A，且 B 资源不可访问。
        3. 键值状态成功恢复为原始内容。
        4. Judge 模型判定测试通过。
    """

    def test_key_value_instance_state_tampering_is_detected(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge,
        repeat_index: int,
    ) -> None:
        self.run_local_instance_tampering_is_detected_and_restored(
            agent_model,
            judge_model,
            VARIANTS[1],
            repeat_index,
        )
