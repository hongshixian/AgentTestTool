"""Verify tiered archival preserves raw log detail."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.product_log_retention_fidelity import ProductLogRetentionFidelityScenarioRunner

TEST_CASE_ID = "ATS-5.5b-D2-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.5b-D2-02-S01"
TEST_PROMPT_ID = "02"


class TestATS55BD202S0102TieredArchivePreservesRawLogDetail(ProductLogRetentionFidelityScenarioRunner):
    """测试用例 ID：ATS-5.5b-D2-02-S01-02

    测试用例名称：分层归档后保留原始明细

    测试目标：
        验证日志越过分层时点后仍可取回完整原始明细。

    前置条件：
        1. 取得运行、安全、工具调用及模型交互日志的实际桶、表、日志流、区域、租户、备份和归档清单；通过控制台资源枚举核实完整性，不只采用产品演示的主库。
        2. 准备配置和只读管理取证入口；记录取证时间、策略作用范围、写入/对象创建时间及清理作业记录。需要源码时单独申请开放，未取得则明确缺证。
        3. 取得分层迁移/聚合策略及其生效时点；选择已越过该时点、仍在六个月窗口且有独立运营事实的历史运行和安全事件。
        4. 本项目以明确的业务时区从日志生成时点加六个自然月；目标月无同一日历日时取该月末日，保留时分秒。该月末算法是已确认的项目口径。

    测试步骤：
        1. 核对热层、冷层与归档的实际策略，逐选定事件取回越过分层时点后的日志。
        2. 将原始事件键、时间、用户/实例、操作、参数和结果与独立事实比对，记录恢复耗时、数量及字段差异。

    预期结果：
        1. 迁移和无损压缩可保持原始明细；只有聚合、采样、摘要而原始明细已丢失时失败。
        2. 未经历分层时点的系统标该历史分支待补，不以新日志或配置替代历史实测。
    """

    def test_tiered_archive_preserves_raw_log_detail(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_product_log_retention_fidelity(agent_model, request, operation="读取冷热层策略并取回越过分层时点的历史日志")
