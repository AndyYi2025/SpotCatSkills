# Quant Root Cause Analysis Protocol

## 触发条件

满足以下任一：
- 同一任务连续 3 次 quality-review 得分 < 9/10
- 同一任务连续 3 轮 implementer 测试失败
- 同一任务总轮次 > 10

## 根因类型（7 种）

| # | 类型 | 修复方式 |
|---|------|---------|
| 1 | 需求不清 | 更新验收标准，返回 implementing |
| 2 | 任务过大 | 拆分为子任务，返回 pending |
| 3 | 技术债务 | 插入清理子任务，返回 implementing |
| 4 | 架构问题 | 标记 blocked |
| 5 | 环境问题 | 修复或标记 blocked |
| 6 | **数据质量问题** | 修复数据路径/来源，验证完整性，返回 implementing |
| 7 | **过拟合** | 简化策略，增加样本外验证，返回 implementing |

## 数据质量问题处理

- 根据项目 CLAUDE.md 验证数据路径
- 检查日期缺失或缺口
- 确认数据是真实的（非合成）
- 修复数据加载逻辑

## 过拟合问题处理

- 审查参数数量 vs 数据大小
- 检查样本内 vs 样本外性能差距
- 简化策略或添加正则化

## 流程

1. 读取 sprint plan 和所有历史尝试记录
2. 识别根因类型
3. 应用修复
4. 更新 sprint plan
5. 记录到 `.learnings/LEARNINGS.md`

## 输出格式

```markdown
### {任务名} — Phase: root-cause — 轮次 {N}

**门控:** PASS — 根因分析完成

#### 根因类型: {类型}

#### 分析过程
{为什么是这个根因}

#### 采取措施
{具体行动}

#### 判定
- next_phase: {implementing|done|blocked}
- root_cause_type: {类型}
```
