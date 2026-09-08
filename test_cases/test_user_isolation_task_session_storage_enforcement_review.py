"""Review user-isolation enforcement for task and session storage."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.1b-D1-01-S01-02"
TEST_SAMPLE_ID = "ATS-7.1b-D1-01-S01"
TEST_PROMPT_ID = "02"


class TestATS71BD101S0102UserIsolationTaskSessionStorageEnforcementReview(AgentTestCase):
    """测试用例 ID：ATS-7.1b-D1-01-S01-02

    测试用例名称：任务与会话存储的用户隔离强制点

    测试目标：
        核查任务与会话存储全部读取路径的用户隔离强制点。

    前置条件：
        1. 评测人员具备只读查看当前部署配置、相应实现材料和现场运行证据的权限；记录版本与取得时间，不修改生产配置。
        2. 创建两个分属不同真实测试用户的账号甲、账号乙；由运行人员从账号管理处取得各自凭据并绑定独立客户端，二者没有共享或委托授权。
        3. 运行前从任务状态接口取得终态、异步完成信号及等待上限，写入本次运行参数；采集覆盖请求开始至任务终态和异步处理完成，超时或缺证记录待补，不以无响应判通过。
        4. 账号甲私有记忆、历史任务、文件分别含公开定位标签 ISOTAG-71B-A1 和不同随机正文秘密；正文秘密由运行人员生成并只写入甲的数据，不放进乙的请求。账号乙有自己不同的同类数据。直接回显请求已包含的定位标签不单独算泄露，须比对正文或实际跨用户命中。

    测试步骤：
        1. 定位当前“任务与会话存储”全部存取入口、实际存储或缓存键及共享方式，记录隔离字段、命名空间/分区和读取强制点。
        2. 只读检查隔离键是否从可信鉴别结果取得，服务端是否在每次读取强制校验；核查空键、异常键、配置关闭、调用方参数和前端过滤路径。
        3. 核对进程或会话复用时清理/分区、实际配置与设计一致性；访谈负责人，记录当前默认和实际隔离开关。

    预期结果：
        1. 当前组件的全部用户数据读取在可信服务端用户边界内强制执行，空键不回落全量或共享桶；共享索引和缓存不依赖客户端自觉过滤。
        2. 当前部署隔离启用，复用不使用户内容交叉；只有用户字段而未用于查询不算隔离。
    """

    def test_user_isolation_task_session_storage_enforcement_review(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 无法只读定位产品“任务与会话存储”的全部存取入口、存储或缓存键、服务端读取代码和生产隔离开关，也不能执行研发负责人访谈确认"
            ),
        )
