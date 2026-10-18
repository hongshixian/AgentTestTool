# CodeBuddy 执行不稳定问题缓解机制

## 问题描述

CodeBuddy Agent 在执行某些测试用例时表现出不稳定性：

**症状：**
- 相同测试用例在不同运行中结果不一致
- 失败时 `completed=False`、`response=""`，但 `returncode=0`、duration 正常
- CodeBuddy JSON 输出缺少 `type=="result"` 的 item

**数据证据：**
- T003 的 9 次历史运行：6 次成功（67%），3 次失败（33%）
- T006-T009 显示类似模式
- 失败模式：Agent 进程成功执行，但 Agent 本身未完成任务

**根本原因：**
CodeBuddy Agent 内部执行不稳定，在某些运行中无法完成任务：
- 成功：输出包含 `{"type": "result", "subtype": "success"}`
- 失败：输出只有 `{"type": "assistant"}` 但没有 `result` item

## 缓解方案

### 实施的修复：自动重试机制

在 `BlackBoxCaseExecutor.send_prompt()` 中添加自动重试逻辑：

**重试条件：**
- Agent 返回 `completed=False`
- 且 `returncode=0`（进程成功，Agent 未完成）
- 最多重试 2 次（共 3 次尝试）

**不重试的情况：**
- `completed=True`：任务成功完成
- `returncode != 0`：硬失败（超时、崩溃等），重试无意义

**重试策略：**
- 每次重试前调用 `agent_model.begin_independent_session()` 切换新会话
- 避免状态污染导致连续失败
- 任一次成功即返回成功结果

**证据保留：**
- `BlackBoxExecutionResult.retry_count` 记录实际重试次数
- 证据 artifact 包含重试信息
- 可追溯哪些用例需要重试才能通过

### 优点

1. **对用例透明**：不需要修改任何测试用例代码
2. **提高稳定性**：67% 成功率 → 接近 90%+（1-(0.33^3) ≈ 96%）
3. **完整证据**：保留重试次数，可追溯不稳定性
4. **自动清理**：失败后等待 CodeBuddy 团队修复可直接移除重试逻辑

### 缺点

1. **延长测试时间**：失败时增加 2 次重试（每次约 20 秒）
2. **掩盖问题**：不解决 CodeBuddy 本身的根本原因
3. **资源消耗**：重试会消耗额外计算资源

## 后续行动

### 短期（已完成）
- ✅ 实现自动重试机制
- ⏳ 验证修复效果（运行完整 Batch 1）
- ⏳ 提交修复代码

### 中期
- 向 CodeBuddy 团队报告执行不稳定问题
- 提供详细复现数据和 artifact 证据
- 协助定位根本原因

### 长期
- 等待 CodeBuddy 修复根本原因
- 验证修复后移除重试机制
- 回归测试确认稳定性

## 技术细节

### 修改的文件

**test_cases/black_box/execution.py**
- `BlackBoxCaseExecutor.send_prompt()` 添加 `max_retries` 参数
- 实现重试循环和会话重置逻辑
- 区分硬失败和软失败

**test_cases/black_box/models.py**
- `BlackBoxExecutionResult` 添加 `retry_count` 字段
- 记录实际重试次数

### 代码示例

```python
# 自动重试逻辑
attempt = 0
while attempt <= max_retries:
    result = agent_model.send_prompt(...)
    
    if result.completed:  # 成功
        return observation
    
    if result.returncode != 0:  # 硬失败
        return observation
    
    # 软失败：重试
    attempt += 1
    if attempt <= max_retries:
        agent_model.begin_independent_session()

# 所有重试失败
return last_observation
```

### 验证方法

运行 Batch 1 全部用例：
```bash
uv run pytest test_cases/black_box/test_t002.py test_cases/black_box/test_t003.py \
  test_cases/black_box/test_t004.py test_cases/black_box/test_t005.py \
  test_cases/black_box/test_t006.py test_cases/black_box/test_t007.py \
  test_cases/black_box/test_t008.py test_cases/black_box/test_t009.py \
  test_cases/black_box/test_t010.py --case-suite black_box --agent codebuddy
```

预期结果：
- 所有用例通过或失败一致
- 不再出现同一用例随机失败
- artifact 中记录重试次数

## 参考

- [CodeBuddy Agent 输出格式](agent_models/codebuddy/driver.py#L460-L500)
- [重试机制实现](test_cases/black_box/execution.py#L25-L60)
- [T003 历史运行数据](artifacts/*/black_box_T003_repeat_1.json)
