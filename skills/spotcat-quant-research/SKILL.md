---
name: spotcat-quant-research
description: "Quant research loop. Automates: hypothesis -> explore -> prototype -> backtest -> evaluate -> report. For exploratory strategy research and validation."
user-invocable: false
type: agent-skill
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
metadata:
  openclaw:
    emoji: "🔬"
    requires:
      bins: []
---

# spotcat-quant-research

Quant research loop skill for OpenClaw agents using ACP continuous coding.

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

## Iron Rules

1. **NO SYNTHETIC DATA** — 永远不使用合成/假数据，所有回测必须用真实市场数据
2. **NO AUTO-TRADING** — 永不自动从 paper 推广到实盘
3. **NEGATIVE RESULTS ARE VALID** — NO-GO 是一个有效的研究结果，不是失败
4. **ASYNC FOR LONG PHASES** — exploring、prototyping、backtesting 异步执行；hypothesis、evaluating、reporting 同步执行

## 状态机

```
hypothesis → exploring → prototyping → backtesting → evaluating → reporting → done/blocked
```

### Phase 详情

**hypothesis**
- Cron turn 内同步执行
- 定义和精化研究假设
- 确定目标市场、数据来源、验收阈值
- 门控：假设精化完成
- 转换到 `exploring`

**exploring**
- 异步 via `sessions_spawn`
- 加载真实数据，计算统计量，识别模式
- 门控：数据从真实路径成功加载
- 转换到 `prototyping`

**prototyping**
- 异步 via `sessions_spawn`
- 构建最小策略原型 + 回测框架
- 门控：代码在样本数据上无错误运行
- 转换到 `backtesting`

**backtesting**
- 异步 via `sessions_spawn`
- 全量历史数据回测
- 多个周期、前向分析（walk-forward）、敏感性分析
- 门控：Sharpe ≥ 最小阈值，无前瞻偏差，真实数据
- 转换到 `evaluating`

**evaluating**
- Cron turn 内同步执行
- 执行评估协议
- 检查过拟合：样本内 vs 样本外，参数敏感性
- 按 research-scoring.md 评分
- Verdict: GO (≥4.0) / NEEDS-WORK (3.0-3.9) / NO-GO (<3.0)
- GO → `reporting`
- NEEDS-WORK → `prototyping` + 反馈
- NO-GO → `reporting`（负结果）

**reporting**
- Cron turn 内同步执行
- 将结构化研究报告写入 research-plan.md
- 包括：假设、方法论、结果、风险、建议
- 转换到 `done`

**done**
- 研究完成（正向或负向结果）
- 报告保存在 research-plan.md

**blocked**
- 需要人工介入
- 无自动转换

## 根因类型（研究特有）

1. **数据不足** — 数据不足以验证假设
2. **假设无效** — 市场行为与预期不符（合法的负结果，不是失败）
3. **过拟合** — 样本内好，样本外差
4. **实现 bug** — 策略逻辑错误，不是假设失败
5. **环境问题** — 数据加载失败，缺少依赖

## 研究评分（5 分制）

| 维度 | 满分 | 焦点 |
|------|------|------|
| Hypothesis clarity | 1.0 | 可测试、具体、可测量 |
| Data rigor | 1.0 | 真实数据、无前瞻、完整日期 |
| Strategy soundness | 1.0 | 逻辑、不曲线拟合、合理假设 |
| Performance | 1.0 | Sharpe、回撤、胜率、交易次数 |
| Robustness | 1.0 | 样本外、参数敏感性、状态稳定性 |

门控：≥4.0 → GO, 3.0-3.9 → NEEDS-WORK, <3.0 → NO-GO

## 安全规则

同 shared/safety-rules.md：
- 禁止合成数据
- 禁止自动交易
- Paper 模式默认
- 凭证通过 env vars

## Cron 配置

- 间隔 1 小时
- 异步 phase（exploring、prototyping、backtesting）：spawn 后返回，下次 cron 检查状态
- 同步 phase（hypothesis、evaluating、reporting）：turn 内完成

触发消息模板:
```
🔬 QUANT RESEARCH — 读取 research-plan.md，执行当前 phase。
研究循环：假设 → 探索 → 原型 → 回测 → 评估 → 报告。
门控: 5 维度评分，≥4.0 = GO，<3.0 = NO-GO（负结果有效）。
```
