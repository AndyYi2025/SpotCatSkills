# {项目名} 冲刺计划

**项目:** {项目名}
**文档:** {文档链接}
**状态:** 活跃
**冲刺周期:** 每小时一轮 SDD phase，≥9 分过关

> 初始状态：所有任务 phase=pending。第一次 cron 运行将最高优先级 pending 任务转为 implementing。
> 任务池表是状态的真实来源。"当前冲刺"摘要表由此派生。

---

## 当前冲刺

| 字段 | 值 |
|------|-----|
| 冲刺编号 | Sprint N |
| 版本目标 | vX.Y.Z |
| 当前任务 | {从任务池 P0 读取} |
| 当前 Phase | {从任务池 P0 读取} |
| 轮次 | {从任务池 P0 读取} |
| Sprint 分支 | {从任务池 sprint_branch 读取} |
| 基准分支 | {从任务池 base_branch 读取} |

---

## 评分记录

| 轮次 | Phase | 任务 | 分数 | 扣分项 | 门控 | 结果 |
|------|-------|------|------|--------|------|------|
| 1 | implementing | {任务} | — | — | 测试全绿 | PASS/RETRY |
| 1 | spec-review | {任务} | X/3.0 | {偏差} | ≥2.5 | PASS/ROLLBACK |
| 1 | quality-review | {任务} | X/10 | {扣分} | ≥9 | PASS/ROLLBACK/ROOTCAUSE |

---

## 任务池

> phase 值: `pending` | `implementing` | `spec-review` | `quality-review` | `root-cause` | `done` | `blocked`

### Sprint N (当前)

| 优先级 | 任务 | 负责人 | Phase | 轮次 | fail_streak | impl_fail | rc_count | task_ref | spawned_at | sprint_branch | base_branch | 状态 |
|--------|------|--------|-------|------|-------------|-----------|----------|----------|------------|---------------|-------------|------|
| P0 | {任务名} | {agent} | pending | 0 | 0 | 0 | 0 | | | | | pending |
| P1 | {任务名} | {agent} | pending | 0 | 0 | 0 | 0 | | | | | pending |
| P2 | {任务名} | {agent} | pending | 0 | 0 | 0 | 0 | | | | | pending |

**字段说明：**
- **Phase**: 当前 SDD 阶段
- **轮次**: 此任务经历的评估/分析周期数
- **fail_streak**: 连续 quality-review <9 的次数
- **impl_fail**: 连续后台 agent 实现失败的次数
- **rc_count**: 根因分析执行次数（信息性）
- **task_ref**: 当前后台任务的 ID
- **spawned_at**: 后台任务启动时间（ISO-8601）
- **sprint_branch**: Sprint 开发分支名（`scsprint/{任务名}`）
- **base_branch**: 原始分支名

---

## 交付记录

<!-- 每次 phase 完成后追加 -->

---

## Review 评分标准

| 维度 | 满分 | 要点 |
|------|------|------|
| 正确性 | 3.0 | 功能完整、API 对齐、无 bug |
| 代码质量 | 2.5 | 类型安全、可读性 |
| 可维护性 | 2.0 | 模块化、文档完整 |
| 测试覆盖 | 1.5 | 单元测试覆盖关键路径 |
| 用户体验 | 1.0 | CLI 输出清晰、错误提示友好 |

**等级:** 9-10 通过 | 7-8 小改 | 5-6 大改 | <5 重做

**SDD 门控:** 测试全绿 → 正确性 ≥2.5/3 → 总分 ≥9/10

---

## 技术栈

- 语言/框架:
- 测试框架:
- 测试命令:
- 配置格式:
- 认证方式:

_Last updated: {日期}_
