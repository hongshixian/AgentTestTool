"""Verify that replacing local identity storage with an unknown identifier cannot impersonate an instance."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1b-D2-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.1b-D2-02-S01"
TEST_PROMPT_ID = "02"


class TestATS51BD202S0102LocalIdentityReplacedWithUnknownID(AgentTestCase):
    """测试用例 ID：ATS-5.1b-D2-02-S01-02

    测试用例名称：端侧存储不存在标识后不冒用身份

    测试目标：
        验证端侧实例标识被替换为格式合法但从未分配的标识后，产品检出异常且不采信构造身份。

    前置条件：
        1. 已准备账号甲、乙及其真实实例、私有便签和专属授权。
        2. 已通过权威实例清单确认构造标识格式合法且从未分配。
        3. 已取得实际执行身份、便签访问和授权记录查询入口。
        4. 已定位端侧标识及校验字段，并完成测试设备和实例甲存储备份。

    测试步骤：
        1. 分别在实例甲、乙写入可区分的私有便签并确认可读。
        2. 停止应用，仅把实例甲的端侧标识改为未分配标识并保持校验值不变。
        3. 重启应用，查询当前便签、识别账号、实际执行身份和授权记录。
        4. 保存篡改内容、响应和校验日志后恢复备份。

    预期结果：
        1. 产品拒绝启动、要求重新鉴别，或创建不继承历史与授权的新实例。
        2. 产品不按构造标识正常运行，也不读取乙的数据或使用乙的授权。
        3. 判定依据是权威执行身份、数据和授权记录，不是界面显示。
        4. 产品崩溃或缺少存储、身份和校验证据不能视为通过。
    """

    def test_unknown_local_identifier_cannot_be_accepted_as_identity(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前没有真实端侧标识定位、应用启停、存储篡改和恢复 Helper 实现，"
                "也不能从权威当前及历史实例清单证明构造标识从未分配，或查询真实执行身份、"
                "数据、授权及校验日志，因此无法执行本行不存在标识篡改路径"
            ),
        )
