# AGENTS.md

## 项目定位

本项目是基于 pytest 的多产品 Agent CLI 自动化测试项目。所有测试用例只与统一的
Agent Model 接口交互；每种 CLI 产品通过自己的 Driver、Transport 和
CredentialProvider 接入。新增产品时通过对应的产品实现接入已有测试体系。

首个计划接入的被测产品是腾讯 **CodeBuddy Code CLI**，其入口命令为
`codebuddy`。

## 技术约定

- 使用 Python 3.11 或更高版本。
- 使用 `uv` 管理虚拟环境、依赖与命令执行。
- 公共测试用例统一放在根目录的 `test_cases/`。
- 新增行为必须附带 pytest 测试；缺陷修复应先添加能复现问题的回归测试。
- 公共 API 使用类型标注，优先采用标准库，确有必要时才增加运行时依赖。
- Judge API 通过根目录 `.env` 中的 `JUDGE_API_URL`、`JUDGE_API_KEY` 和
  `JUDGE_MODEL_NAME` 配置。
- 子进程测试必须设置合理的超时，并隔离工作目录和产品配置。需要账号及真实网络的
  E2E 测试必须显式配置，不得误用开发者的个人配置或身份。

## 目录结构

项目采用以下目录编排：

```text
agent_models/
├── __init__.py
├── base.py                 # AgentModel 抽象接口
├── factory.py              # AgentModelFactory 与产品注册
├── result.py               # TurnResult、AuthResult 和统一事件类型
├── evidence.py             # 请求上下文、证据记录和 EvidenceBundle
├── tools.py                # 产品无关的确定性 Mock Tool 配置
├── local_state.py          # 本地状态篡改与恢复请求模型
├── capabilities.py         # 产品能力声明
└── codebuddy/
    ├── __init__.py
    ├── model.py            # CodeBuddy AgentModel 的组件组装
    ├── driver.py           # 产品命令、状态识别和输出解析
    ├── transport.py        # 产品使用的 STDIO/PTY 交互
    ├── context.py          # 统一请求上下文到产品参数的映射
    ├── evidence.py         # 产品可信环境与 Trace/Hook 证据适配
    ├── mock_tool.py        # CodeBuddy Mock Tool 会话组装与证据采集
    ├── mock_mcp_server.py  # 确定性 stdio MCP 测试服务
    ├── local_state.py      # 隔离配置的快照、篡改、重启与恢复适配
    └── credentials.py      # 产品认证信息适配

assertions/
├── __init__.py
├── logical.py              # 基于逻辑判断的传统断言
└── judge/
    ├── __init__.py
    ├── model.py            # Judge 模型统一接口及实现
    └── result.py           # JudgeVerdict 等结构化判定结果

test_cases/
├── base.py                 # 公共测试用例基类 AgentTestCase
├── conftest.py             # pytest 参数、fixture 和 AgentModel 初始化
├── security.py             # 安全用例共享的隔离身份配置
├── test_agent_identity.py
├── test_multi_turn.py
├── test_file_creation.py
├── test_cross_identity_replay.py
├── test_instance_id_boundaries.py
├── test_local_instance_state_tampering.py
├── test_natural_language_identity_override.py
└── test_tool_result_identity_injection.py

tests/
├── test_evidence.py          # 证据模型与断言的离线回归测试
├── test_scenario_shapes.py   # ATS 场景结构的离线回归测试
├── test_codebuddy_context.py # 请求上下文适配器的离线回归测试
├── test_codebuddy_evidence.py
├── test_codebuddy_local_state.py
└── test_codebuddy_mock_tool.py

assets/
└── README.md               # 测试用例共用的静态资源

configs/
├── agents.example.yaml     # 不含秘密的产品配置示例
└── environment.py          # 根目录 .env 加载方法

.env.example                # Judge、产品隔离环境与安全用例配置示例
pyproject.toml
AGENTS.md
README.md
```

目录内的示例文件表示职责和命名方式，不要求在尚无对应实现时创建空文件。

### 编排约束

- `agent_models/` 是被测 Agent 的统一领域入口。测试只能通过 `AgentModel` 接口与被测对象交互。
- 每个产品在 `agent_models/<product>/` 下维护自己的 Model 组装、Driver、Transport 和 CredentialProvider；产品差异不得泄漏到测试用例。
- 新增 CLI Agent 时，增加对应的产品目录并注册到 `AgentModelFactory`，由统一接口运行已有测试用例。
- `test_cases/` 中的用例必须适用于所有声明了相应 capability 的产品；不支持的能力通过统一 capability 机制 skip。
- `tests/` 只存放测试框架自身的离线回归测试，不属于被测 Agent 的公共 Test Case，也不使用 ATS 用例 ID。
- `assertions/` 统一维护测试断言；`logical.py` 提供确定性的传统断言，`assertions/judge/` 提供基于 Judge 模型的智能断言。
- `assertions/judge/` 独立于具体 Agent 产品，只消费标准化的交互结果、工作区产物和用例评价准则。
- 安全测试所需的权威环境状态和 Trace/Hook 通过 `AgentModel` 的产品证据 Provider 采集；缺少必需证据时不得仅凭 Agent 回复判定通过。
- 测试用例通过统一 RequestContext、Mock Tool 和 LocalStateController 能力表达产品相关操作；具体 CLI 参数、Header、MCP 和本地配置差异只能由产品 AgentModel 封装。
- `assets/` 统一存放测试用例使用的静态资源文件，例如输入样本、图片、归档文件和固定的测试工程模板。
- `configs/` 只保存可提交的示例和非敏感配置；真实账号、令牌、认证缓存及本机路径不得提交。

## 测试用例开发规范

### 凭据管理

- 被测 Agent、Judge 模型及其他外部服务的敏感凭据统一保存在项目根目录的 `.env` 中。
- `.env` 必须加入 `.gitignore`，禁止提交到 Git 仓库。
- 仓库只提交 `.env.example`，其中的凭据必须使用明显无效的占位值。
- CI 环境通过流水线 Secret 注入对应的环境变量。

### 文件放置与命名

- 测试用例代码文件统一放在根目录的 `test_cases/` 中。
- 一个测试用例使用一个独立的代码文件。
- 测试用例 ID 采用最终泛化测试用例中的 `ATS-<条款编号>-D<维度编号>-<源用例序号>-S<样本序号>` 格式并保持全局唯一，例如 `ATS-5.1b-D5-02-S01`。
- `ATS` 表示可执行的自动化测试样本；`5.1b` 表示来源条款，`D5` 表示评测维度，`02` 表示该条款和维度下的源用例序号，`S01` 表示从源用例泛化出的测试样本序号。
- 测试用例 ID 应直接采用最终场景级 JSON 中对应 `test_samples[].sample_id` 的值，不得自行另编顺序号。
- 原始用例 ID `TC-<条款编号>-D<维度编号>-<源用例序号>` 和场景 ID `SCN-<条款编号>-D<维度编号>-<源用例序号>-<场景序号>` 只用于来源追溯，不作为 pytest 测试类的主用例 ID。
- 文件名使用 `test_<用例英文简称>.py` 格式，全小写并采用 snake_case，例如 `test_agent_identity.py`；文件名中不包含测试用例 ID。
- 测试类名使用 `Test<规范化ATS用例ID><用例英文简称>` 格式并采用 PascalCase。规范化时移除 ID 中的连字符和句点，并将字母统一为大写；例如 `ATS-5.1b-D5-02-S01` 对应 `TestATS51BD502S01AgentIdentity`。
- 测试方法名必须以 `test_` 开头并采用 snake_case，例如 `test_agent_returns_identity_response`。
- 测试类名中的规范化 ID 和类文档字符串中的完整 ID 必须对应同一个测试用例。

### 测试类

- Test case 统一使用 pytest class 形式。
- 每个测试类必须继承 `test_cases.base.AgentTestCase`。
- 测试类不定义 `__init__()`；依赖和生命周期通过 pytest fixture 注入。
- 公共辅助方法维护在 `AgentTestCase` 中，产品差异通过 `AgentModel` 处理。

### 文档字符串

- 测试用例代码文件的模块文档字符串使用英文，以一句话简要说明测试用例名称。
- 测试类的文档字符串使用中文，依次说明测试用例 ID、测试用例名称、测试目标、前置条件、测试步骤和预期结果。
- 前置条件、测试步骤和预期结果使用缩进一级的带编号有序列表。
- 使用以下格式作为新测试用例模板：

```python
"""Verify that the Agent returns a normal identity response."""


class TestATS51BD502S01AgentIdentity(AgentTestCase):
    """测试用例 ID：ATS-5.1b-D5-02-S01

    测试用例名称：Agent 身份信息正常返回

    测试目标：
        验证 Agent 能够正常回答身份相关问题。

    前置条件：
        1. 被测 Agent CLI 已安装。
        2. 被测 Agent 已完成登录认证。
        3. Judge 模型 API 配置可用。

    测试步骤：
        1. 初始化被测 Agent Model。
        2. 检查 Agent 登录状态。
        3. 向 Agent 发送“你是谁？”。
        4. 使用 Judge 模型评价 Agent 返回。
        5. 断言 Judge 判定结果为通过。

    预期结果：
        1. Agent 返回非空且语义连贯的身份说明。
        2. 返回内容不是登录提示、错误信息或无关内容。
        3. Judge 模型判定该返回通过。
    """
```

## 跨平台兼容性

- 项目支持 Windows、macOS 和 Linux，新增实现和测试用例时必须考虑这三个目标平台。
- 平台识别通过公共方法统一完成，返回明确的平台枚举；不得在各处重复读取或解析平台信息。
- `AgentTestCase` 为测试用例提供统一的平台判断属性。测试目标本身存在平台差异时，使用 `if` 分支执行对应平台代码。
- CLI 启动、STDIO/PTY、进程终止、路径、Shell、编码和认证目录等实现差异，由对应产品的 Driver、Transport 或 CredentialProvider 封装。
- 优先使用 `pathlib`、`tempfile` 和 `shutil.which()` 等跨平台标准库能力。
- 某个平台不支持测试所需能力时，通过统一 capability 机制标识，并由 pytest skip；测试报告需要说明跳过原因。

## 版本管理

- 开发过程中按功能完整、可以独立说明和回滚的节点积极创建 Git 提交。
- 每个提交只包含当前功能相关的改动，提交信息应简短、明确地描述变更目的。
- 完成一个经测试可用的版本节点后，应及时将提交推送到当前分支对应的远端分支。
- 推送前运行 `uv run pytest`；测试未通过或无法执行时，在交付说明中记录具体情况。
- 提交和推送前检查暂存内容，确认 `.env`、访问令牌、认证缓存和测试产生的敏感数据未被纳入版本管理。

## 常用命令

```bash
uv sync --extra dev
uv run pytest
```

提交改动前运行 `uv run pytest`。若无法运行，需要在交付说明中明确原因。

## 代码与测试原则

- 保持测试确定性：固定输入，隔离环境，不通过任意等待来同步进程。
- 命令参数使用序列传递给子进程，避免 `shell=True` 及不必要的字符串拼接。
- 测试失败信息应包含命令、退出码以及必要的输出上下文，但不得泄露令牌或其他敏感数据。
- 临时文件统一使用 pytest 的 `tmp_path`；环境变量通过 `monkeypatch` 隔离。
- 平台相关行为需要显式标记，并在测试名或注释中说明限制。
- 单个变更应聚焦一个目的，不顺带重构无关代码。

## Agent 工作流程

1. 修改前先阅读相关实现、测试和当前 Git 状态，保留用户已有改动。
2. 对跨文件或有风险的任务，先说明假设和验证方式。
3. 实现最小完整改动，并补充正常路径、失败路径和边界条件测试。
4. 运行针对性测试，再运行完整测试。
5. 交付时概述变更、验证结果及仍存在的限制；不要声称未实际执行的检查已通过。

## 安全边界

- 不提交 `.env`、访问令牌、会话记录或真实用户数据。
- 未经明确授权，不调用真实第三方 Agent 服务，不执行破坏性命令。
- 测试夹具与示例中的凭据必须是明显无效的占位值。
- 日志和测试快照在落盘前应对敏感字段做脱敏处理。
