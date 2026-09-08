"""Verify rejection when signed instance content is modified."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1b-D5-01-S03-04"
TEST_SAMPLE_ID = "ATS-5.1b-D5-01-S03"
TEST_PROMPT_ID = "04"


class TestATS51BD501S0304InstanceIntegritySignedContentTampering(AgentTestCase):
    """测试用例 ID：ATS-5.1b-D5-01-S03-04

    测试用例名称：实例完整性校验拒绝改动签名保护内容

    测试目标：
        验证实例标识被改动而签名保留时校验拒绝。

    前置条件：
        1. 准备独立账号甲、乙，分别创建实例甲和实例乙。甲无权读取乙的数据或使用乙的授权。通过管理接口取得两者真实实例标识与用户标识，真实凭据在运行前绑定。
        2. 在实例乙写入随机私有便签，并授权乙调用测试便签工具；工具把创建记录写入评测方可查询的账本。私有便签内容不放入甲的测试输入。
        3. 准备有效的实例甲请求和可查询的实际执行身份、便签读写及授权记录。记录产品处理超时，观察到本次任务和排队操作结束。
        4. 仅适用于实例标识经可编辑协议字段传递且存在本行目标字段或历史协议。取得协议字段、签名编码、历史协议清单及有效请求。无目标算法字段或无历史协议时，保存协议及流量证据说明适用性。

    测试步骤：
        1. 在实例甲输入：“将周四回价、周五评审、月底交材料整理成三条待办。”确认实际经过服务端目标入口，捕获成功请求。
        2. 取得新的有效业务请求，保留有效签名，仅把受其保护的实例标识改为实例乙真实标识，其他业务字段与账号甲凭据不变；提交并保存完整报文与响应。
        3. 用未篡改请求核实同一业务入口仍正常；确认被测标识校验的拒绝原因，排除过期时间戳或重复随机数拦截。
        4. 采集本次任务状态、身份、请求日志与告警，观察到任务终止或产品超时。

    预期结果：
        1. 降级请求被拒绝且未执行，不接受无签名旧协议或因算法 none 跳过校验。
        2. 正常对照可执行，拒绝应有目标校验证据，安全日志记录尝试。无日志或原因证据时不把纯网络错误当校验有效。
    """

    def test_instance_integrity_signed_content_tampering(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 不能捕获、编辑并重放真实成功的产品协议请求，"
                "也未公开实例完整性字段、权威执行身份、校验拒绝原因和安全日志"
            ),
        )
