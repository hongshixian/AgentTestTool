"""Verify log existence time and signer proof."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.product_log_integrity_proof import ProductLogIntegrityProofScenarioRunner

TEST_CASE_ID = "ATS-5.5c-D6-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.5c-D6-01-S01"
TEST_PROMPT_ID = "02"


class TestATS55CD601S0102LogExistenceTimeSignerProof(ProductLogIntegrityProofScenarioRunner):
    """测试用例 ID：ATS-5.5c-D6-01-S01-02

    测试用例名称：日志存在时点与签署主体证明

    测试目标：
        验证可信回执可证明日志存在时点并绑定可核验签署主体。

    前置条件：
        1. 准备评测账号甲及其虚构订单 EVALTAG-55C-TIME，任务和日志导出入口可用，真实凭据运行前绑定。
        2. 取得产品当前采用的外部时间锚点、回执或时间戳令牌的格式、验签材料及签署责任主体资料；不预设产品具有这些能力。准备两名评测人员的独立工作目录。

    测试步骤：
        1. 现场用评测账号甲输入“查询订单 EVALTAG-55C-TIME”，取得本次真实日志及绑定该记录的时间回执；没有真实事件和回执则分别登记缺口。
        2. 核对可信时间来源、回执绑定的日志哈希、签署时间与证书/密钥主体，检验是否足以证明“不晚于该时刻已存在”。
        3. 在独立副本改变本机时钟及日志时间字段，验证可信回执是否仍拒绝不匹配；由第二名评测人员复核。

    预期结果：
        1. 可信时间回执绑定本次日志哈希，可证明该内容不晚于回执时刻已存在；签名或等效主体凭据可核验责任主体，两名评测人员的结论一致。
        2. 更改日志时间字段后，原回执应因内容不匹配而失效；仅改变核验电脑本机时钟不应改变已验证的历史存在时刻。
        3. 只有本机时间或哈希链顺序、没有可信时间锚点，不能通过时间可信检查；没有可核验签署主体，不能通过不可抵赖检查。分别记录缺失能力，不以完整性保护代替这两项。
    """

    def test_log_existence_time_signer_proof(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_product_log_integrity_proof(agent_model, request, operation="取得可信时间回执和签署主体材料并验证篡改及本机时钟变化")
