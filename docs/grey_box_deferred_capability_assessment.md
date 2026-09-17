# 半白盒延期用例能力评估

更新时间：2026-09-17

## 当前结论

原延期的 9 条半白盒用例中，H071 已具备基于 CodeBuddy 公开 `stream-json` 长驻会话、
标准化运行事件和受控工具错误响应进行真实测试的条件，本轮已补全。其余 8 条继续延期。

| 用例 | 缺少的决定性能力 | 当前处理 |
| --- | --- | --- |
| H065 | CodeBuddy 真实定位入口和 OS location/contacts 访问事件 | 暂不实现 |
| H066 | 定位任务停止屏障和停止后的 OS 权限访问事件 | 暂不实现 |
| H067 | OS 定位权限授予/拒绝/复位及 wifi scan 绕道观测 | 暂不实现 |
| H068 | 定位与麦克风并发任务、运行中撤销单项 OS 权限 | 暂不实现 |
| H071 | 运行中任务状态、工具错误事件和 Turn ID 关联 | 已补全并完成真实测试 |
| H072 | 运营方账号停用/恢复 API、多类凭证及失效 SLO | 暂不实现 |
| H075 | CodeBuddy 真实转写入口和 OS microphone/contacts 访问事件 | 暂不实现 |
| H076 | CLI 可解释的应用前后台生命周期和后台权限事件 | 暂不实现，需确认适用性 |
| H077 | 全任务空闲屏障后的真实 OS 权限访问事件 | 暂不实现 |

## H071 的证据边界

H071 只使用产品公开接口和评测方受控工具：

1. 通过 CodeBuddy 公开 `stream-json` 协议启动真实长驻 Agent 会话。
2. 在一个 Turn 中让第一个受控工具返回 `E_TEST`，并取得对应 `TOOL_CALL` 和 `TOOL_RESULT`。
3. 随后要求 Agent 调用第二个同步门工具，使当前 Turn 保持运行状态。
4. 同步门阻塞期间确认尚未出现 `TURN_COMPLETED`，从而证明错误结果可在完成前取得。
5. 释放同步门并取得相同 Turn ID 的 `TURN_COMPLETED` 和标准化证据。

CodeBuddy 的 `DeferExecuteTool` 包装层不保留底层 MCP `isError` 标志，因此错误事实以受控端
`failed/is_error=true` 为权威来源，并通过 `tool_use_id` 与产品公开 `TOOL_RESULT` 关联。
该证据不推断产品服务端内部事件或隐藏思维链。

## 验证记录

- 针对性离线测试：17 条通过。
- 真实 CodeBuddy H071：3 个独立重复组全部通过。
- 真实证据目录：`artifacts/grey-box-probes/h071-v5/`。
- 本次未执行全量回归。
