# AgentTestTool

一个基于 pytest、面向多种 Agent CLI 产品的自动化测试项目。测试用例只与统一的
Agent Model 接口交互，每种产品通过自己的 Driver、Transport 和
CredentialProvider 接入。

首个计划接入的被测产品是腾讯 **CodeBuddy Code CLI**（命令为 `codebuddy`）。

## 快速开始

```bash
uv sync --extra dev
# 默认执行完整测试，包括真实 Agent CLI 和 Judge E2E 用例
uv run pytest --agent=codebuddy

# 需要稳定性验证时，将支持重复执行的测试路径运行三次
uv run pytest --agent=codebuddy --repeat=3

# 开发阶段执行快速单元测试和冒烟测试
uv run pytest --smoke --agent=codebuddy
```

`--repeat=COUNT` 控制支持重复执行的测试路径的运行次数，`COUNT` 必须是正整数。
未传入该参数时默认只运行一次。

完整测试需要先配置真实测试账号、CodeBuddy 登录状态和 Judge API。`--smoke` 会执行
身份响应、文件创建和多轮会话三条冒烟测试，因此也会调用真实 Agent 和 Judge。

Judge 使用 OpenAI 兼容的 Chat Completions API，并从项目根目录的 `.env` 读取：

```dotenv
JUDGE_API_URL=https://example.com
JUDGE_API_KEY=your-api-key
JUDGE_MODEL_NAME=infi/deepseek-v4-flash
```

`.env` 已被 Git 忽略，只用于当前测试环境。

## 真实账号安全测试

安全用例直接运行真实 Agent CLI、真实网络服务和专用真实测试账号。账号 A 是执行测试的
登录账号，账号 B 是受保护目标。测试数据应专门创建并可安全清理，不得使用个人日常账号
或生产业务数据。

CodeBuddy 官方通过 `CODEBUDDY_CONFIG_DIR` 选择配置目录。先使用该目录完成账号 A 的
产品登录流程，再在 `.env` 中配置同一路径；框架会把它传给每个 CodeBuddy 子进程：

```dotenv
CODEBUDDY_CONFIG_DIR=/path/to/real-account-a-codebuddy-config
AGENT_TEST_A_USER_ID=real-test-user-a
AGENT_TEST_A_INSTANCE_ID=real-test-instance-a
AGENT_TEST_B_USER_ID=real-test-user-b
AGENT_TEST_B_INSTANCE_ID=real-test-instance-b
```

账号 B 需要预置 JSON 用例约定的私有标记 `IDB-DATA-73` 和实例授权标记
`AUTH-B-29`，并确认账号 A 通过产品正常权限边界无法访问它们。

S01–S05 按完整用例评价真实身份、数据访问和授权边界。执行前要求产品明确支持
`security_boundary_observation`，且真实 A/B 身份和所需测试资源已准备。
S04、S05 可继续使用当前已登录的账号 A；B 标识必须显式配置，不使用虚构目标替代。

当前 CodeBuddy 可完整执行三条冒烟用例。13 条安全路径按 capability 跳过：
S01、S02 缺少公开的用户或实例上下文选择能力；S03 缺少可用的本地状态控制适配；
S04、S05 以及其他安全路径还缺少完整安全边界观察能力。历史上的回复和 Mock Tool
检查通过只代表局部检查通过，不代表完整安全用例通过。

需要比较真实账号或资源的执行前后状态时，可配置 `CODEBUDDY_OBSERVATION_COMMAND`。
该命令只能调用第三方用户可访问的公开 CLI、网页或 API，并通过 JSON 标准输入输出交换
观察结果；不得依赖产品内部 Trace、Hook 或私有测试接口。

配置观察命令只表示具备证据采集入口，不会自动启用完整安全边界能力。产品适配需要先
验证真实身份使用、B 数据访问和授权调用/复用的全过程证据，并补齐相应断言；Agent
自述、前后状态相同或未发现成功授权不能替代这些证据。

S03 通过 `CODEBUDDY_LOCAL_STATE_COMMAND` 对专用账号 A 的可恢复配置副本执行快照、
篡改、重启和恢复。S05 使用 CodeBuddy 公开的 `--mcp-config` 接入确定性 stdio MCP
Server，并记录第三方测试端可观察的工具输入和输出。

## 目录结构

```text
agent_models/   Agent Model 抽象与各 CLI 产品实现
assertions/      传统逻辑断言及 Judge 智能断言
test_cases/     pytest 公共测试用例
assets/         测试用例共用静态资源
configs/        产品配置示例
AGENTS.md       Agent 协作与开发约定
```
