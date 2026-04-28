---
type: agent-skill
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
metadata:
  openclaw:
    emoji: "🎯"
    requires:
      bins: []
---

# spotcat-quant-dev

Quant-adapted Spec-Driven Development skill for OpenClaw agents using ACP continuous coding.

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

## Iron Rules

1. **NO TASK TRANSITION WITHOUT PASSING REVIEW** — 当前任务 quality-review 总分 <9/10 不能进下一任务
2. **NO FIXES WITHOUT ROOT CAUSE** — 连续 3 轮 quality-review <9，或连续 3 轮 implementer 测试失败，必须根因分析
3. **ALL 3 TEST LAYERS MUST PASS** — unit tests + backtest + data validation，缺一不可
4. **IMPLEMENTING 异步，REVIEWING 同步连续** — implementing 通过 `sessions_spawn` 异步执行；spec-review、quality-review、root-cause 在 cron turn 内同步执行

## 约定

- **技术标识符**用英文：phase 名、字段名、命令输出
- **说明文字**用中文：指令描述、评分说明
- Phase 值：`pending` / `implementing` / `spec-review` / `quality-review` / `root-cause` / `done` / `blocked`
- Emoji 仅用于人类可读性，自动化逻辑用纯文本 phase 值判断
- **Sprint 分支：** 每个任务在 `scsprint/{任务名}` 分支上开发，完成后 merge 回原始分支

## 状态机流程 (SDD)

Same 6-phase state machine as spotcat-sprint-dev:

```
pending → implementing → spec-review → quality-review → root-cause → done/blocked
```

### Phase 差异（与 spotcat-sprint-dev 对比）

**pending:**
- 读取 quant-sprint-plan.md 获取任务定义
- 加载项目 quant context（数据路径、市场规则、风险参数）
- 从项目 CLAUDE.md 读取数据路径并验证

**implementing:**
- 按 quant-implementer-prompt.md 执行
- 必须完成所有 3 层测试（见 quant-gates.md）
- 后台 agent 通过 `sessions_spawn` 异步执行

**spec-review:**
- 按 quant-spec-reviewer-prompt.md 执行
- 必须验证：策略逻辑、数据完整性、无合成数据
- 正确性 ≥ 2.5/3.0 才能进下一 phase

**quality-review:**
- 按 quant-quality-reviewer-prompt.md 执行
- 评分按 quant-scoring.md（10 分制）
- 3 层测试门控必须全部通过（见 quant-gates.md）
- 安全规则违反：总分归零（veto）
- 总分 ≥ 9/10 才能 done

**root-cause:**
- 按 quant-root-cause-analysis.md 执行
- 7 种根因类型（原 5 种 + 2 种量化特有）：
  1. 需求不清
  2. 任务过大
  3. 技术债务
  4. 架构问题
  5. 环境问题
  6. **数据质量问题** — 错误/过时数据、缺失日期、错误路径
  7. **过拟合** — 回测表现好但策略不稳健

**done:**
- 代码 merge 到 base_branch
- 删除 sprint 分支
- 注意：paper trading 和实盘部署是手动步骤，agent 不自动推进

## 3 层测试门控

详见 `references/quant-gates.md`：

1. **Unit Tests** — 逻辑正确性、边缘情况、错误处理
2. **Backtest** — 真实数据上的策略表现（Sharpe、回撤、无前瞻偏差）
3. **Data Validation** — 数据来源和完整性（正确路径、日期完整、无合成数据）

全部 3 层通过才能 quality-review PASS。

## 安全边界

Agent 永不自动从 paper 推广到实盘。Sprint 在 done = 代码合并 + 回测通过 结束。Paper → real 始终是人工决策。

## Cron 配置

同 spotcat-sprint-dev：
- 间隔 1 小时
- implementing 异步（sessions_spawn，上限 1.5h）
- spec-review、quality-review、root-cause 同步

触发消息模板:
```
🎯 QUANT SPRINT — 读取 quant-sprint-plan.md，定位最高优先级未完成任务。
3 层测试门控：unit tests + backtest + data validation。
门控: 测试全绿 → 正确性 ≥2.5 → 总分 ≥9。连续失败触发根因分析。
```
