# AgentTestTool

一个基于 pytest、面向多种 Agent CLI 产品的自动化测试项目。测试用例只与统一的
Agent Model 接口交互，每种产品通过自己的 Driver、Transport 和
CredentialProvider 接入。

首个计划接入的被测产品是腾讯 **CodeBuddy Code CLI**（命令为 `codebuddy`）。

## 快速开始

```bash
uv sync --extra dev
uv run pytest --agent=codebuddy
```

Judge 使用 OpenAI 兼容的 Chat Completions API，并从项目根目录的 `.env` 读取：

```dotenv
JUDGE_API_URL=https://example.com
JUDGE_API_KEY=your-api-key
JUDGE_MODEL_NAME=infi/deepseek-v4-flash
```

`.env` 已被 Git 忽略，只用于当前测试环境。

## 目录结构

```text
agent_models/   Agent Model 抽象与各 CLI 产品实现
assertions/      传统逻辑断言及 Judge 智能断言
test_cases/     pytest 公共测试用例
configs/        产品配置示例
AGENTS.md       Agent 协作与开发约定
```
