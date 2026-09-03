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
├── conftest.py             # pytest 参数、fixture 和 AgentModel 初始化
├── test_authentication.py
├── test_basic_conversation.py
├── test_multi_turn.py
├── test_file_creation.py
└── test_code_modification.py

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
