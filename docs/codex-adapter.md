# Codex CLI 适配说明

适配器通过公开的 `codex exec` 子命令接入，每个回合启动一个独立进程，不需要常驻服务。

## 安装与认证

不固定版本，使用本机已安装的 `codex`。驱动只记录实际版本，不做版本门禁。

评测方不管理认证：Codex 直接使用操作者已登录的 `CODEX_HOME`（默认 `~/.codex`），
驱动不执行 login/logout，也不修改用户的 `config.toml`。所有测试参数都通过 `-c` 临时覆盖。

可选的 `.env` 配置：

```dotenv
CODEX_BIN=codex
CODEX_TEST_MODEL=gpt-6-luna
CODEX_TEST_REASONING_EFFORT=high
```

运行方式：

```bash
uv run agent-test --agent codex --suite black_box
```

## 运行方式

- 新会话：`codex exec --color never --cd <工作区> -m <模型> -c model_reasoning_effort=... --json -o <文件> -- <prompt>`
- 续接：`codex exec --color never resume ... -- <thread_id> <prompt>`。`resume` 不接受 `--cd` 和 `-s`，沙箱用 `-c sandbox_mode=...` 指定。
- 回答正文取 `-o` 写出的最后一条消息；完成状态以退出码和 JSONL 中的 `turn.completed` 为准。
- JSONL 里 `item.type=error` 的条目是用户配置告警，不算回合失败。
- 多轮需要保存会话才能续接，因此会话文件会写入用户的 `~/.codex/sessions`。认证检查使用 `--ephemeral`。

## 环境隔离

Codex 执行 shell 时默认继承全部环境变量。驱动用白名单环境启动子进程（`PATH`、`HOME`、`LANG`、
`CODEX_HOME` 和代理变量），并设置 `shell_environment_policy.inherit="core"`，
Judge 和其他产品的密钥不会出现在 Agent 可见的环境中。

## 权限

无头模式没有逐次审批通道，`approval_policy` 固定为 `never`，按 `PermissionPolicy` 选择沙箱：

| PermissionPolicy | Codex 参数 |
| --- | --- |
| `allow_tools=False` / DENY_UNAPPROVED | `sandbox_mode="read-only"` |
| ALLOW_WORKSPACE_EDITS | `sandbox_mode="workspace-write"` |
| BYPASS | `--dangerously-bypass-approvals-and-sandbox` |
| 评测方 Mock MCP | `default_tools_approval_mode="approve"` |

`permission_event_evidence` 声明为不支持。Codex 自带 Linux 沙箱，本机没有系统 bwrap 时也能生效；
`workspace-write` 默认允许写 `/tmp`。

## Mock MCP

通过 `-c mcp_servers.ats_mock.*` 注入 stdio 桥（复用 `agent_models/codebuddy/mock_mcp_server.py`），
用 `enabled_tools` 限定可见工具。未设置 `default_tools_approval_mode="approve"` 时，
`approval_policy=never` 会直接拒绝 MCP 调用。
