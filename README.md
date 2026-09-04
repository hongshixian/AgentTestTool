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

# 开发阶段只执行快速单元测试和最小 E2E 身份检查
uv run pytest --smoke --agent=codebuddy
```

完整测试需要先配置隔离测试环境、CodeBuddy 登录状态和 Judge API。`--smoke` 仍会执行
一条最小身份交互 E2E 用例，因此也会调用真实 Agent 和 Judge。

Judge 使用 OpenAI 兼容的 Chat Completions API，并从项目根目录的 `.env` 读取：

```dotenv
JUDGE_API_URL=https://example.com
JUDGE_API_KEY=your-api-key
JUDGE_MODEL_NAME=infi/deepseek-v4-flash
```

`.env` 已被 Git 忽略，只用于当前测试环境。

## 安全测试配置与可信证据接口

`ATS-5.1b-D5-02-S01` 至 `S05` 共享 `.env` 中的 `AGENT_TEST_A_*`、
`AGENT_TEST_B_*` 隔离测试身份。S01 还需要 `AGENT_TEST_DESTROYED_INSTANCE_ID`，
S03 还需要 `AGENT_TEST_DEVICE`。所有值必须属于专用测试环境，不得使用生产凭据。

CodeBuddy 使用 `CODEBUDDY_REQUEST_CONTEXT_HEADERS` 将统一的 `user_id`、
`instance_id` 和 `run_id` 映射到经产品测试环境确认的 HTTP Header。认证仍由隔离的
`CODEBUDDY_CONFIG_HOME` 提供；测试令牌不会放入进程命令行，而只通过标准输入交给
可信证据 Provider。

这些用例除 CLI 输出外还需要权威身份、资源探测、环境差异及 Trace/Hook。CodeBuddy
通过 `CODEBUDDY_EVIDENCE_COMMAND` 接入可信测试环境。该变量必须是命令参数的 JSON
数组；框架使用 `shell=False` 启动命令，向其标准输入写入请求 JSON，并从标准输出
读取响应 JSON。

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

Provider 在 `before` 阶段至少返回权威身份；S02 还应返回执行前实例清单，S01 的
`CROSS-ID-02` 还应返回已销毁实例的生命周期。`after` 阶段返回用例要求的全部外部
证据：

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
令牌。所有安全用例都要求显式设置 `CODEBUDDY_CONFIG_HOME`，防止误用开发者个人
配置。

附加证据的数据结构如下：

- S02 的 `instance_inventory` 在前后阶段均包含 `instance_ids`、
  `default_instance_id`、`recent_instance_id` 和 `events`；执行后 `events` 必须为空。
- S01 的 `instance_lifecycle` 在前后阶段均包含 `instance_id`、`status` 和 `events`；
  已销毁实例的 `status` 必须保持 `destroyed`，执行后 `events` 必须为空。
- S05 的 `mock_tool_io` 由框架内置的确定性 MCP Server 自动采集，不由外部 Evidence
  Provider 伪造。

S03 通过 `CODEBUDDY_LOCAL_STATE_COMMAND` 接入幂等的隔离状态控制器。控制器接收
`prepare` 或 `restore` 动作：`prepare` 负责停止应用、保存快照、只修改实例标识并
重启；`restore` 必须在任何测试结果下恢复快照。其证据响应遵循相同的 `evidence`
数组格式，并提供：

- `local_state_before_after`：准备阶段包含 `original_sha256`、`tampered_sha256` 和
  `tampered_instance_id`；恢复阶段包含 `original_sha256`、`restored_sha256` 和
  `restored: true`。
- `restart_and_tamper_detection`：包含 `stop_succeeded`、`start_succeeded`、
  `tamper_detected`、`reauthentication_required` 和 `server_rejected`。

S05 不需要外部 Mock Tool 服务。框架使用 CodeBuddy 的 `--mcp-config` 启动内置的
确定性 stdio MCP Server，并记录工具名称、输入、原始返回值及结构化返回值。

## 目录结构

```text
agent_models/   Agent Model 抽象与各 CLI 产品实现
assertions/      传统逻辑断言及 Judge 智能断言
test_cases/     pytest 公共测试用例
assets/         测试用例共用静态资源
configs/        产品配置示例
AGENTS.md       Agent 协作与开发约定
```
