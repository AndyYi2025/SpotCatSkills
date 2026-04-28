# {项目名} 量化冲刺计划

**项目:** {项目名}
**状态:** 活跃
**冲刺周期:** 每小时一轮 SDD phase，≥9 分过关

> 初始状态：所有任务 phase=pending。
> 任务池表是状态的真实来源。

---

## Quant Context

- Market: {market} (CN Future / CN Stock / US Stock / US Option)
- Data paths: {data_paths}
- Backtest framework: {backtest_framework}
- Test command: {test_command}
- Backtest command: {backtest_command}

## Risk Parameters

- Min Sharpe: {min_sharpe}
- Max drawdown: {max_drawdown}
- Min trade count: {min_trades}
- Position limit: {position_limit}

---

## 评分记录

| 轮次 | Phase | 任务 | 分数 | 3层测试 | 门控 | 结果 |
|------|-------|------|------|---------|------|------|
| 1 | implementing | {任务} | — | — | 3层全绿 | PASS/RETRY |
| 1 | spec-review | {任务} | X/3.0 | — | ≥2.5 | PASS/ROLLBACK |
| 1 | quality-review | {任务} | X/10 | PASS/FAIL | ≥9 | PASS/ROLLBACK/ROOTCAUSE |

---

## 任务池

> phase 值: `pending` | `implementing` | `spec-review` | `quality-review` | `root-cause` | `done` | `blocked`

### Sprint N (当前)

| 优先级 | 任务 | Phase | 轮次 | fail_streak | impl_fail | rc_count | task_ref | spawned_at | sprint_branch | base_branch | 状态 |
|--------|------|-------|------|-------------|-----------|----------|----------|------------|---------------|-------------|------|
| P0 | {任务名} | pending | 0 | 0 | 0 | 0 | | | | | ⏳ |

---

## 交付记录

<!-- 每次 phase 完成后追加 -->
