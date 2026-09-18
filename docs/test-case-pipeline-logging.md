# 测试用例执行流水线日志规范

所有黑盒、灰盒和白盒用例使用 `EvidenceLedger` 保存规范化流水线事件。事件的
`source` 固定为 `test_case_pipeline`，协议版本为 `1.0`。

## 生命周期事件

- `case_started`：用例隔离环境创建完成。
- `phase_started`：一个流水线阶段开始。
- `phase_completed`：阶段正常结束，可包含四态结果。
- `phase_failed`：阶段因未处理异常失败。
- `phase_not_applicable`：能力或前置条件不足，阶段不适用。
- `case_completed`：用例已经产生最终四态结论。

## 标准阶段

阶段按实际需要记录，不要求每种卷产生没有执行过的空阶段：

1. `initialize`
2. `capability_check`
3. `environment_setup`
4. `evidence_collection`
5. `exercise`
6. `evidence_projection`
7. `assertion`
8. `cleanup`
9. `conclusion`

## 公共字段

阶段事件的 `data` 统一包含：

- `schema_version`
- `case_id`
- `case_level`
- `repeat_index`
- `phase`
- `duration_seconds`（终态事件）
- `status` 和 `reason`（存在四态结论时）
- `evidence_ids`
- `artifact_refs`

同一阶段的开始和终态事件共享 `correlation_id`，格式为：

```text
<case_id>:repeat-<repeat_index>:<phase>
```

事件在写入前由 `EvidenceLedger` 脱敏，并进入同一运行的哈希链。卷别差异仅影响
实际执行和证据内容：黑盒不得引用 Trace，灰盒可以记录网络与重建 Trace，白盒
占位用例在 `capability_check` 阶段记录 `phase_not_applicable`。
