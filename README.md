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

# 开发阶段只执行快速单元测试和最小 E2E 身份检查
uv run pytest --smoke --agent=codebuddy
```

`--repeat=COUNT` 控制支持重复执行的测试路径的运行次数，`COUNT` 必须是正整数。
未传入该参数时默认只运行一次。

完整测试需要先配置真实测试账号、CodeBuddy 登录状态和 Judge API。`--smoke` 仍会执行
一条最小身份交互 E2E 用例，因此也会调用真实 Agent 和 Judge。

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

S04、S05 在账号 A 的真实认证会话中执行自然语言和 Mock Tool 注入。S01、S02 需要产品
公开的用户或实例上下文选择参数；CodeBuddy 当前没有对应的公开 CLI 能力，因此这些路径
会通过 capability 机制跳过，不会通过自定义 HTTP Header 伪造身份。

需要比较真实账号或资源的执行前后状态时，可配置 `CODEBUDDY_OBSERVATION_COMMAND`。
该命令只能调用第三方用户可访问的公开 CLI、网页或 API，并通过 JSON 标准输入输出交换
观察结果；不得依赖产品内部 Trace、Hook 或私有测试接口。

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
