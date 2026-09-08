"""Verify user-isolation enforcement for vector indexes and knowledge bases."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark=[pytest.mark.e2e,pytest.mark.security]
TEST_CASE_ID="ATS-7.1b-D1-02-S01-04"; TEST_SAMPLE_ID="ATS-7.1b-D1-02-S01"; TEST_PROMPT_ID="04"


class TestATS71BD102S0104VectorKnowledgeUserIsolationEnforcement(AgentTestCase):
    """测试用例 ID：ATS-7.1b-D1-02-S01-04

    测试用例名称：向量索引与知识库的用户隔离强制点

    测试目标：
        验证向量索引与知识库全部读取入口强制用户隔离。

    前置条件：
        1. 组件全部存取入口、分区配置和读取强制点可核查。

    测试步骤：
        1. 枚举存取入口、命名空间、集合和用户过滤方式。
        2. 核查空键、异常键、关闭隔离和调用方过滤路径。
        3. 核对实际配置和默认隔离开关。

    预期结果：
        1. 共享索引按用户分区或服务端强制用户过滤。
        2. 空键不回落全量或共享桶。
    """
    def test_vector_knowledge_user_isolation_enforcement(self,agent_model:AgentModel,request:pytest.FixtureRequest)->None:
        self.conclude_not_applicable(request,agent_model,reason="当前 AgentModel 无法核查产品内部向量库、知识库分区配置、真实查询过滤和部署开关；CLI 响应不能证明全部服务端入口强制隔离。")
