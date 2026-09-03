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
├── capabilities.py         # 产品能力声明
└── codebuddy/
    ├── __init__.py
    ├── model.py            # CodeBuddy AgentModel 的组件组装
    ├── driver.py           # 产品命令、状态识别和输出解析
    ├── transport.py        # 产品使用的 STDIO/PTY 交互
    └── credentials.py      # 产品认证信息适配

judge/
├── __init__.py
├── model.py                # Judge 模型统一接口及实现
└── result.py               # JudgeVerdict 等结构化判定结果

test_cases/
├── base.py                 # 公共测试用例基类 AgentTestCase
├── conftest.py             # pytest 参数、fixture 和 AgentModel 初始化
├── test_atc_001_agent_identity.py
├── test_atc_002_multi_turn.py
└── test_atc_003_file_creation.py

configs/
└── agents.example.yaml     # 不含秘密的产品配置示例

.env.example                # Judge API 环境变量示例
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
- `judge/` 独立于具体 Agent 产品，只消费标准化的交互结果、工作区产物和用例评价准则。
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
- 测试用例 ID 使用 `ATC-三位数字` 格式并保持唯一，例如 `ATC-001`。
- 文件名使用 `test_atc_<三位数字>_<用例英文简称>.py` 格式，全小写并采用 snake_case，例如 `test_atc_001_agent_identity.py`。
- 测试类名使用 `TestATC<三位数字><用例英文简称>` 格式并采用 PascalCase，例如 `TestATC001AgentIdentity`。
- 测试方法名必须以 `test_` 开头并采用 snake_case，例如 `test_agent_returns_identity_response`。
- 文件名、测试类名和类文档字符串中必须使用同一个测试用例 ID。

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


class TestATC001AgentIdentity(AgentTestCase):
    """测试用例 ID：ATC-001

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
