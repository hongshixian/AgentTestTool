# QwenPaw 适配说明

QwenPaw 是本地运行的 Agent 框架。它不通过 CLI 交互，而是提供 REST/SSE 控制台 API。
适配器以 `agent_models/qwenpaw/` 的形式接入统一的 `AgentModel` 接口，公共用例不需要修改。

## 安装与配置

只支持固定版本 `qwenpaw==2.2.1`，请装在独立环境里，不要装进本项目依赖：

```bash
uv venv --python 3.11 ~/.local/share/agent-test-tool/qwenpaw-2.2.1
uv pip install --python ~/.local/share/agent-test-tool/qwenpaw-2.2.1/bin/python "qwenpaw==2.2.1"
```

在项目根目录的 `.env` 中设置：

```dotenv
QWENPAW_BIN=/path/to/qwenpaw-2.2.1/bin/qwenpaw
QWENPAW_TEST_MODEL=infi/glm-5.3-flash
QWENPAW_TEST_API_KEY=your-dedicated-test-api-key   # 未设置时回退到 IIIS_API_KEY
# QWENPAW_TEST_BASE_URL=https://router.ai.iiis.co:9443/v1
```

版本不是 2.2.1 时，`check_installation()` 报告"未安装"，冒烟门禁因此不通过。

运行方式：

```bash
uv run agent-test --agent qwenpaw --suite black_box --business-workers 2
```

## 运行方式

每个 Model 都会启动一个独立的 QwenPaw 实例，各自使用私有的工作目录、凭据目录和随机回环端口，用例结束后整组进程被清理。
初始化不需要打开 Console UI，按以下顺序完成：

1. `qwenpaw init --defaults --accept-security`
2. `qwenpaw models add-provider` 和 `models add-model`
3. 在 `agent.json` 中写入 `approval_level=STRICT`，并把 `project_dir` 设为评测方工作区
4. 启动 `qwenpaw app`
5. 用回环 REST 接口写入 API Key（QwenPaw 会加密落盘），再激活模型

API Key 不会出现在 QwenPaw 的进程环境变量或命令行参数中。

`approval_level` 和 `project_dir` 必须在启动前写入。启动后再通过 REST 修改会触发异步的 Agent
重载，导致刚注册的 MCP 驱动失效。

QwenPaw 自身的状态文件（`MEMORY.md`、`sessions/`、`history.db` 等）位于私有工作目录，不在评测方工作区内，
因此工作区快照只包含用例文件和 Agent 的工具副作用。

## 权限

所有回合都在 STRICT 级别下运行，每次工具调用都会进入 `/api/approval`。驱动按用例声明的
`PermissionPolicy` 逐次批准或拒绝，并把每次决定作为证据存档：

| 工具类别 | DENY_UNAPPROVED | ALLOW_WORKSPACE_EDITS | BYPASS |
| --- | --- | --- | --- |
| 读取（Read/Glob/Grep 等） | 允许 | 允许 | 允许 |
| 写入（Write/Edit/Append） | 拒绝 | 仅限评测方工作区内 | 允许 |
| Shell、网络、子 Agent 等 | 拒绝 | 拒绝 | 允许 |
| 评测方 Mock MCP（`ats_mock`） | 允许 | 允许 | 允许 |

`allow_tools=False` 时拒绝所有工具。单轮调用不支持 `ASK`；交互式会话（`start_session`）尚未实现，
相应能力已声明为不支持。

## 证据边界

- 回答正文只取 SSE 中 `type=message` 的内容，思考过程和工具输出不计入。
- 工具调用和输出按 `call_id` 配对，保存在 `raw_output` 中；黑盒卷不会把它归档。
- 被停止的回合，SSE 终态仍是 `completed`。驱动把超时记为未完成，以 `/api/console/chat/stop` 的返回值作为中断证据。
- 产品默认沙箱后端取决于宿主机。本机未装 bwrap 时为 none，评测方不额外添加沙箱。
- `write_file` 写 `.txt` 文件时会加 UTF-8 BOM。公共用例按 `utf-8-sig` 读取，BOM 视为编码标记，不算内容。
- 控制台 API 是单用户模式，请求体里的 `user_id` 由调用方自报，不作为鉴别身份。

接入前的实测记录见 `local_docs/国内外4个工作和编码agent黑盒测评文档/QwenPaw接入前实测结论.md`（不纳入版本管理）。
