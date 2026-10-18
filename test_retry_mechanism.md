# CodeBuddy 执行不稳定问题与缓解方案

## 问题分析

### 症状
- 相同测试用例在不同运行中结果不一致
- 失败时 `completed=False`、`response=""`，但 `returncode=0`、duration 正常
- CodeBuddy 输出缺少 `type=="result"` 的 item

### 根本原因
CodeBuddy Agent 本身执行不稳定，在某些运行中无法完成任务：
- 成功：输出包含 `{"type": "result", "subtype": "success"}`
- 失败：输出只有 `{"type": "assistant"}` 但没有 `result` item

### 数据证据
T003 的 9 次运行：
- 6 次成功（67%）：completed=True，有完整 response
- 3 次失败（33%）：completed=False，response 为空

其他用例显示类似模式。

## 缓解方案

### 方案 1：测试层自动重试（推荐）
在 BlackBoxCaseExecutor.execute() 中增加重试逻辑：
- 检测 completed=False 且 returncode=0 的情况
- 自动重试最多 2 次
- 记录重试次数到 metrics
- 任一次成功即返回成功结果

优点：
- 对用例透明，不影响现有测试代码
- 提高测试稳定性
- 保留完整重试证据

缺点：
- 延长单个测试时间（失败时）
- 不解决 CodeBuddy 本身的问题

### 方案 2：增加 CodeBuddy 超时时间
当前所有用例 timeout=120s，可能不足。

缺点：
- 延长所有测试时间
- 不能解决非超时导致的失败

### 方案 3：标记已知不稳定用例
在用例 metadata 中标记 `unstable: true`，报告时单独统计。

缺点：
- 不解决问题，只是记录
- 降低测试权威性

## 建议行动

1. **立即**：实现方案 1 的自动重试机制
2. **短期**：向 CodeBuddy 团队报告执行不稳定问题
3. **长期**：等待 CodeBuddy 修复根本原因后移除重试机制
