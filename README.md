# AgentTestTool

一个基于 pytest、面向多种 Agent CLI 产品的自动化测试项目。测试用例只与统一的
Agent Model 接口交互，每种产品通过自己的 Driver、Transport 和
CredentialProvider 接入。

首个计划接入的被测产品是腾讯 **CodeBuddy Code CLI**（命令为 `codebuddy`）。

## 快速开始

```bash
uv sync --extra dev
uv run pytest
```

默认测试命令不会调用真实 Agent 或 Judge。显式配置隔离测试环境后，使用以下命令运行
E2E 用例：

```bash
uv run pytest --run-e2e --agent=codebuddy
```

Judge 使用 OpenAI 兼容的 Chat Completions API，并从项目根目录的 `.env` 读取：

```dotenv
JUDGE_API_URL=https://example.com
JUDGE_API_KEY=your-api-key
JUDGE_MODEL_NAME=infi/deepseek-v4-flash
```

`.env` 已被 Git 忽略，只用于当前测试环境。

## S04 可信证据接口

`ATS-5.1b-D5-02-S04` 除 CLI 输出外还需要权威身份、资源探测、环境差异及
Trace/Hook。CodeBuddy 通过 `.env` 中的 `CODEBUDDY_EVIDENCE_COMMAND` 接入可信
测试环境。该变量必须是命令参数的 JSON 数组；框架使用 `shell=False` 启动命令，向
其标准输入写入请求 JSON，并从标准输出读取响应 JSON。

执行前请求示例：

```json
{
  "sample_id": "ATS-5.1b-D5-02-S04",
  "prompt_id": "LANGUAGE-01",
  "repeat_index": 1,
  "phase": "before",
  "request_context": {
    "authorization": "Bearer <test-token>",
    "user_id": "test-user-a",
    "instance_id": "test-instance-a",
    "run_id": "<unique-run-id>"
  },
  "session_id": null
}
```

Provider 在 `before` 阶段至少返回权威身份，在 `after` 阶段返回全部外部证据：

```json
{
  "evidence": [
    {
      "evidence_id": "authoritative_identity_observation",
      "type": "environment_observation",
      "data": {"user_id": "test-user-a", "instance_id": "test-instance-a"}
    },
    {
      "evidence_id": "resource_probe_result",
      "type": "environment_observation",
      "data": {"observed_private_markers": [], "successful_authorizations": []}
    },
    {
      "evidence_id": "environment_state_diff",
      "type": "environment_observation",
      "data": {"identity_changed": false}
    },
    {
      "evidence_id": "internal_trace_or_hook",
      "type": "trace_or_hook",
      "data": {
        "adopted_user_ids": ["test-user-a"],
        "adopted_instance_ids": ["test-instance-a"],
        "data_reads": [],
        "successful_authorizations": []
      }
    }
  ]
}
```

Provider 是可信测试基础设施，会通过标准输入接收测试凭据。其实现和日志必须避免输出
令牌。S04 还要求显式设置 `CODEBUDDY_CONFIG_HOME`，防止误用开发者个人配置。

## 目录结构

```text
agent_models/   Agent Model 抽象与各 CLI 产品实现
assertions/      传统逻辑断言及 Judge 智能断言
test_cases/     pytest 公共测试用例
assets/         测试用例共用静态资源
configs/        产品配置示例
AGENTS.md       Agent 协作与开发约定
```
