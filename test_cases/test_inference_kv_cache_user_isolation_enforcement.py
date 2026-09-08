"""Verify user-isolation enforcement for inference KV caches."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark=[pytest.mark.e2e,pytest.mark.security]
TEST_CASE_ID="ATS-7.1b-D1-02-S01-05"; TEST_SAMPLE_ID="ATS-7.1b-D1-02-S01"; TEST_PROMPT_ID="05"


class TestATS71BD102S0105InferenceKVCacheUserIsolationEnforcement(AgentTestCase):
    """测试用例 ID：ATS-7.1b-D1-02-S01-05

    测试用例名称：推理 KV Cache的用户隔离强制点

    测试目标：
        验证推理 KV Cache 的键和复用流程强制用户隔离。

    前置条件：
        1. 缓存全部入口、真实键、部署配置和复用清理可核查。

    测试步骤：
        1. 枚举缓存入口、用户维度和共享方式。
        2. 核查空键、异常键和关闭隔离路径。
        3. 核对进程或会话复用前的清理与分区。

    预期结果：
        1. 缓存键含可信用户维度且空键不回落共享缓存。
        2. 复用不导致用户上下文交叉。
    """
    def test_inference_kv_cache_user_isolation_enforcement(self,agent_model:AgentModel,request:pytest.FixtureRequest)->None:
        self.conclude_not_applicable(request,agent_model,reason="当前 AgentModel 无法核查产品内部推理 KV Cache 的真实键、服务端强制点、复用清理和部署开关；新 CLI 会话不能证明缓存隔离。")
