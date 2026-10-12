# OpenClaw 适配说明

OpenClaw 2026.8.35 是本地安装的 Agent 框架，提供公开 CLI。适配器通过
`openclaw agent --local` 以嵌入式模式运行，不连接 Gateway，不需要常驻服务进程。

## 安装与配置

只支持固定版本 `2026.8.35`，请装在独立目录里，不要装进本项目依赖：

```bash
npm install --prefix ~/.local/share/agent-test-tool/openclaw-2026.8.35 \
  openclaw@2026.8.35
```

Node.js 要求 `>=24.16 <25` 或 `>=26.1`。本机需要 Node 在 PATH 里。

在项目根目录的 `.env` 中设置：

```dotenv
OPENCLAW_BIN=~/.local/share/agent-test-tool/openclaw-2026.8.35/node_modules/.bin/openclaw
OPENCLAW_TEST_MODEL=infi/glm-5.3-flash
OPENCLAW_TEST_API_KEY=your-dedicated-test-api-key   # 未设置时回退到 IIIS_API_KEY
# OPENCLAW_TEST_BASE_URL=https://router.ai.iiis.co:9443/v1
```

版本不是 `2026.8.35` 时，`check_installation()` 报告"未安装"，冒烟门禁因此不通过。

运行方式：

```bash
uv run agent-test --agent openclaw --suite black_box
```

## 运行方式

每次调用 `send_prompt()` 都启动一个新的 `openclaw agent --local` 进程，使用私有的
状态目录和配置文件。每个 `OpenClawAgentModel` 实例拥有：

- 一个私有临时目录（`OpenClawDriver._root`）：保存配置文件、状态、运行记录
- OpenClaw home 和 state 目录：通过 `OPENCLAW_HOME` / `OPENCLAW_STATE_DIR` 指向私有目录
- 私有配置文件（0600）：含内联 API Key，每次调用前写入，调用后删除

初始化无需打开 Control UI 或 Gateway，驱动直接调用：

```
openclaw agent --local --session-id <id> --message-file <prompt.txt> --json --timeout <n>
```

会话续接通过 `--session-id` 实现：同一 `session_id` 传给连续的调用，OpenClaw 从状态
目录中恢复上一轮的上下文。`begin_independent_session()` 重置 session_id，开始新对话。

## 安全与隔离

**API Key 处理**：Key 直接内联写入 0600 私有配置文件，不使用 `${VAR}` 引用方式——
后者会被 exec 工具的子进程通过继承环境变量的方式读取。驱动用 `env -i` 风格的最小
白名单环境启动产品进程，子进程不继承测试框架的任何密钥。

**工作区限制**：配置中 `tools.fs.workspaceOnly: true` 限制文件工具只能访问 `--cwd`
指定的评测方工作区；跨目录访问（如 `/etc/hostname`）会被产品拒绝。

**Bootstrap 文件**：配置中 `agents.defaults.skipBootstrap: true`，不在工作区写入
AGENTS.md、SOUL.md 等初始化文件。

## 权限

没有逐次审批通道（不连 Gateway），权限通过 `tools.deny` 在配置层声明。驱动按
`PermissionPolicy` 在每次调用前更新配置：

| 工具类别 | DENY_UNAPPROVED | ALLOW_WORKSPACE_EDITS | BYPASS |
| --- | --- | --- | --- |
| 读取（read/glob/grep 等） | 允许 | 允许 | 允许 |
| 写入（write/edit/apply_patch） | 拒绝 | 仅限工作区内（`workspaceOnly`） | 允许 |
| Shell/网络/会话（group:runtime 等） | 拒绝 | 拒绝 | 允许 |
| 评测方 Mock MCP（ats_mock） | 允许 | 允许 | 允许 |
| always denied（automation/messaging/nodes/ui） | 拒绝 | 拒绝 | 拒绝 |

`allow_tools=False` 时拒绝所有工具（`tools.deny: ["*"]`）。

`permission_event_evidence` 声明为不支持，黑盒卷不受影响。

## Mock MCP

MCP 服务通过配置文件中 `mcp.servers.ats_mock` 的 stdio 方式注册，使用
`agent_models/codebuddy/mock_mcp_server.py` 作为桥接器，和 QwenPaw 共用同一
bridge 脚本。工具名称带有 `ats_mock__` 前缀（OpenClaw 自动加上客户端名称）。

不可见工具（`visible_tool_names` 之外）通过 `tools.deny: ["ats_mock__<name>"]` 隐藏。

## 证据边界

- 回答正文取自 `payloads[].text`（JSON 信封中的 `final` 字段等价物），不含工具输出。
- 工具名称取自 `meta.agentMeta.terminalReceipt.successfulToolNames`，只有成功调用。
- 无逐次权限决定证据，`permission_decisions` 记录不生成。
- 产品沙箱默认关闭（无 bwrap/Docker），评测方不额外添加沙箱，记录为 `off`。
- 不写 Bootstrap 文件，工作区快照只包含用例文件和工具副作用。

接入前的实测记录见 `local_docs/国内外4个工作和编码agent黑盒测评文档/OpenClaw接入可行性分析.md`
（不纳入版本管理）。
