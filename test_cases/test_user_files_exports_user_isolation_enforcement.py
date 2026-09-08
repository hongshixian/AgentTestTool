"""Verify user-isolation enforcement for user files and exports."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark=[pytest.mark.e2e,pytest.mark.security]
TEST_CASE_ID="ATS-7.1b-D1-02-S01-03"; TEST_SAMPLE_ID="ATS-7.1b-D1-02-S01"; TEST_PROMPT_ID="03"


class TestATS71BD102S0103UserFilesExportsUserIsolationEnforcement(AgentTestCase):
    """测试用例 ID：ATS-7.1b-D1-02-S01-03

    测试用例名称：用户文件及导出目录的用户隔离强制点

    测试目标：
        验证用户文件和导出目录全部读取入口强制用户隔离。

    前置条件：
        1. 组件全部存取入口、存储键、部署配置和读取强制点可核查。

    测试步骤：
        1. 枚举存取入口、隔离字段、命名空间和共享方式。
        2. 核查空键、异常键、关闭隔离和调用方过滤路径。
        3. 核对复用清理、实际配置和默认隔离开关。

    预期结果：
        1. 全部读取均服务端强制隔离，空键不回落共享数据。
        2. 当前部署启用隔离且复用不导致用户内容交叉。
    """
    def test_user_files_exports_user_isolation_enforcement(self,agent_model:AgentModel,request:pytest.FixtureRequest)->None:
        self.conclude_not_applicable(request,agent_model,reason="当前 AgentModel 无法枚举或只读核查产品全部文件存取入口、服务端隔离键和部署开关；评测工作区独立不能证明产品用户文件与导出隔离。")
