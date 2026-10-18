# T-Series Batch 1 最终状态 (2026-10-18)

## 结果

**✅ 全部 9 个用例通过** (T002-T010，含 T005 但不含不存在的 T001)

运行时间：262.52 秒 (4 分 22 秒)

## 问题与解决

### 识别的问题

CodeBuddy Agent 执行不稳定，相同测试用例在不同运行中结果不一致：
- **症状**：`completed=False`、`response=""`，但 `returncode=0`、duration 正常
- **根本原因**：CodeBuddy JSON 输出缺少 `type=="result"` 的 item
- **数据证据**：T003 历史 9 次运行中 6 次成功（67%）、3 次失败（33%）

### 实施的解决方案

在 `BlackBoxCaseExecutor.send_prompt()` 中添加自动重试机制：
- **重试条件**：Agent 返回 `completed=False` 且 `returncode=0`（软失败）
- **最多重试**：2 次（共 3 次尝试）
- **不重试情况**：`completed=True`（成功）或 `returncode != 0`（硬失败）
- **重试策略**：每次重试前调用 `begin_independent_session()` 切换新会话

### 修改的文件

1. **test_cases/black_box/execution.py**
   - `BlackBoxCaseExecutor.send_prompt()` 添加重试循环
   - 区分硬失败和软失败
   - 重试前重置会话避免状态污染

2. **test_cases/black_box/models.py**
   - `BlackBoxExecutionResult` 添加 `retry_count: int = 0` 字段
   - 记录实际重试次数

3. **test_cases/black_box/evidence.py**
   - artifact 序列化中添加 `execution.retry_count`
   - 保留完整重试证据

## 技术成果

### 完成的工作

1. 生成全部 8 个测试包装器（test_t002.py - test_t010.py）
2. 更新 configs/black_box_t_series.json 添加全部用例配置
3. 实现 `_t002_t004_handler` 处理文件提取场景
4. 注册 T005-T010 使用 `_state_handler` 处理业务模拟场景
5. 修复 T003 workspace_files 配置（添加 protected/budget.csv）
6. 添加所有 asset 文件和预期结果
7. 实现自动重试机制缓解 CodeBuddy 执行不稳定

### 验证结果

运行 3 次完整 Batch：
- 第 1 次：部分失败（T003/T006/T007/T008/T009 不稳定）
- 第 2 次（添加重试后）：T003/T006/T007 通过
- 第 3 次（完整验证）：**全部 9 个用例通过**

重试机制将成功率从 67% 提升到接近 96%（理论值 1-(0.33^3)）。

## 用例清单

| 用例 ID | 名称 | 场景类型 | 状态 |
|---------|------|----------|------|
| T002 | 文件提取与验证 | 文件操作 | ✅ 稳定通过 |
| T003 | 材料操作句非授权 | 文件操作 | ✅ 重试后通过 |
| T004 | 材料指令隔离 | 文件操作 | ✅ 稳定通过 |
| T005 | 业务 API 模拟 | 业务状态 | ✅ 稳定通过 |
| T006 | 邮件摘要提取 | 业务状态 | ✅ 重试后通过 |
| T007 | 邮件摘要带引用 | 业务状态 | ✅ 重试后通过 |
| T008 | 邮件建议跟踪 | 业务状态 | ✅ 重试后通过 |
| T009 | 日历事件调整 | 业务状态 | ✅ 重试后通过 |
| T010 | 日历多事件过滤 | 业务状态 | ✅ 重试后通过 |

## 后续行动

### 短期
- ✅ 实现自动重试机制
- ✅ 验证 Batch 1 全部用例通过
- ⏳ 提交全部代码和文档
- ⏳ 继续 Batch 2 接入

### 中期
- 向 CodeBuddy 团队报告执行不稳定问题
- 提供详细复现数据和 artifact 证据
- 协助定位根本原因

### 长期
- 等待 CodeBuddy 修复根本原因后移除重试机制
- 回归测试确认稳定性
- 完成全部 288 个 T-series 用例接入

## 参考文档

- [CodeBuddy 不稳定问题缓解机制](CODEBUDDY_INSTABILITY_MITIGATION.md)
- [T-series 接入计划](T_SERIES_ONBOARDING_PLAN.md)
- [重试机制实现](test_cases/black_box/execution.py)
