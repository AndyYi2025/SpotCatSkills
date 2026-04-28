---
version: "0.2.1"
description: "当 cron 触发且 sprint-plan.md 存在且任务处于 pending/implementing/spec-review/quality-review/root-cause 阶段时触发。SDD 子代理驱动开发流水线。"
user-invocable: false
type: agent-skill
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
metadata:
  openclaw:
    emoji: "🎯"
    requires:
      bins: []
---

# spotcat-sprint-dev — SDD 多轮冲刺开发

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

## Iron Rules

1. **NO TASK TRANSITION WITHOUT PASSING REVIEW** — 当前任务 quality-review 总分 <9/10 不能进下一任务
2. **NO FIXES WITHOUT ROOT CAUSE** — 连续 3 轮 quality-review <9，或连续 3 轮 implementer 测试失败，必须根因分析
3. **IMPLEMENTING 异步，REVIEWING 同步连续** — implementing 通过 `sessions_spawn` 异步执行；spec-review、quality-review、root-cause 在 cron turn 内同步连续执行（可在一个 turn 内连续执行多个 reviewing phase）

## 约定

- **技术标识符**用英文：phase 名、字段名、命令输出
- **说明文字**用中文：指令描述、评分说明
- Phase 值：`pending` / `implementing` / `spec-review` / `quality-review` / `root-cause` / `done` / `blocked`
- Emoji 仅用于人类可读性，自动化逻辑用纯文本 phase 值判断
- **Sprint 分支：** 每个任务在 `scsprint/{任务名}` 分支上开发，完成后 merge 回原始分支。分支名中的 `/` 和空格替换为 `-`

## 触发条件

本技能由 Cron 触发，满足以下条件时激活：

1. `sprint-plan.md` 存在且可解析（含必要字段：任务池表、phase 列）
2. 有任务的 phase 不是 `done` 或 `blocked`
3. 无其他 agent 正在写 sprint-plan.md（通过文件锁或 OpenClaw cron 串行化保证）
4. **全局并发检查：** 当前项目中 running 状态的 sprint 后台 agent 不超过 `MAX_PARALLEL_IMPL`（默认 4）

不满足条件时：静默退出。如果 sprint-plan.md 格式异常，记录错误到 `.learnings/ERRORS.md` 后退出。

## 状态机流程 (SDD)

每次 cron 触发，读取 sprint-plan.md，定位最高优先级的未完成任务（phase 不是 `done`/`blocked`），根据其 `phase` 执行对应流程。如有多个同优先级任务，选任务池中排列最前的。

### Sprint 分支管理

每个任务在独立的 `scsprint/{任务名}` 分支上开发，隔离改动：

- **创建分支：** pending→implementing 时，cron 记录当前分支为 `base_branch`，创建 `scsprint/{sanitized_task_name}` 分支
- **工作分支：** implementer 在 `scsprint/` 分支上 commit 和修改
- **清理分支：** 失败重试时 reset 分支（`git checkout . && git clean -fd`）；done 时 merge 回 `base_branch` 并删除 sprint 分支
- **分支名 sanitize：** 任务名中的 `/`、空格、特殊字符替换为 `-`，全小写

> 任务池表中 `base_branch` 字段记录原始分支名，`sprint_branch` 字段记录 `scsprint/xxx` 分支名。

```
Cron 触发
    ↓
读取并验证 sprint-plan.md
    ↓ 验证失败 → 记录错误到 .learnings/ → 输出错误到 stderr → 退出
    ↓
定位最高优先级未完成任务
    ↓
根据 phase 分发:
    ↓
┌────────────────────────────────────────────────────────┐
│ phase: pending                                              │
│   → 检查全局并发: running 的 sprint agent 是否 < MAX_PARALLEL_IMPL? │
│     → 超限 → 跳过本轮，等下次 cron                          │
│   → 记录 base_branch = 当前分支名                           │
│   → 创建 sprint_branch = scsprint/{sanitized_task_name}   │
│   → git checkout -b {sprint_branch}                         │
│   → 改为 implementing，spawn 后台 agent 执行               │
│   → 记录 task_ref、spawned_at、sprint_branch 到任务池       │
│   → 本轮结束（不等后台 agent）                               │
├────────────────────────────────────────────────────────┤
│ phase: implementing                                         │
│   → 确认当前在 sprint_branch 上（不在则 checkout）           │
│   → 检查 task_ref 对应的后台任务状态                          │
│   → 后台任务 running 且 spawned_at 未超 1.5h?               │
│     → 跳过，本轮结束                                        │
│   → 后台任务 succeeded?                                     │
│     → 读取后台 agent 的交付记录                              │
│     → 测试全绿? → impl_fail 重置为 0                        │
│       → 清空 task_ref/spawned_at                            │
│       → phase 改为 spec-review                              │
│     → 测试失败? → impl_fail +1                              │
│       → impl_fail ≥ 3? → phase 改为 root-cause              │
│       → 否则 → git checkout . && git clean -fd 清理         │
│         → 重新 spawn（新 task_ref/spawned_at）              │
│   → 后台任务 failed/timed_out?                              │
│     → impl_fail +1                                          │
│     → impl_fail ≥ 3? → phase 改为 root-cause                │
│     → 否则 → git checkout . && git clean -fd → 重新 spawn  │
│   → spawned_at 超过 1.5h? → 视为超时                         │
│     → cancel 后台任务，impl_fail +1                          │
│     → impl_fail ≥ 3? → phase 改为 root-cause                │
│     → 否则 → git checkout . && git clean -fd → 重新 spawn  │
│   → task_ref 为空（旧数据迁移）? → 视为 pending，重新 spawn  │
├────────────────────────────────────────────────────────┤
│ phase: spec-review                                          │
│   → 执行 Spec Reviewer phase（cron turn 内同步）            │
│   → 正确性 ≥ 2.5/3?                                         │
│     → phase 改为 quality-review（同 turn 内继续）            │
│   → < 2.5?                                                  │
│     → phase 改回 implementing + 记录偏差                    │
│     → spawn 后台 agent，记录新 task_ref/spawned_at           │
├────────────────────────────────────────────────────────┤
│ phase: quality-review                                       │
│   → 执行 Quality Reviewer phase（cron turn 内同步）         │
│   → 安全问题? → 总分 = 0，phase 打回 implementing            │
│     → spawn 后台 agent，记录新 task_ref/spawned_at           │
│   → 总分 ≥ 9? → git checkout base_branch                    │
│     → git merge sprint_branch                               │
│     → git branch -d sprint_branch                           │
│     → phase 改为 done，清空 sprint_branch/base_branch       │
│     → 下一任务 phase=pending（等下次 cron 触发）              │
│   → < 9? → 记录扣分 → phase 改回 implementing               │
│     → spawn 后台 agent，记录新 task_ref/spawned_at           │
│   → 读 fail_streak，+1 写回                                  │
│   → fail_streak ≥ 3? → phase 改为 root-cause                │
├────────────────────────────────────────────────────────┤
│ phase: root-cause                                           │
│   → 执行根因分析协议（cron turn 内同步，本轮内完成）          │
│   → 记录到 .learnings/                                      │
│   → 读 rc_count，+1 写回（信息性）                           │
│   → 根因类型为架构问题或不可修复环境?                         │
│     → git checkout base_branch                              │
│     → git branch -D sprint_branch（删除未合并的 sprint 分支）│
│     → phase 改为 blocked，清空 sprint_branch/base_branch    │
│     → 跳到下一任务                                          │
│   → 否则（可自主修复的根因）                                 │
│     → 执行修复措施（拆任务/改需求/清债务/修环境）            │
│     → phase 改回 implementing，重置 fail_streak=0             │
│     → spawn 后台 agent，记录新 task_ref/spawned_at           │
├────────────────────────────────────────────────────────┤
│ phase: blocked                                              │
│   → 跳过此任务，处理下一个未完成任务                           │
├────────────────────────────────────────────────────────┤
│ 所有任务 phase=done                                          │
│   → 生成冲刺总结                                             │
│   → openclaw cron remove {cron-id}（自删除，不再触发）       │
│   → 退出                                                     │
├────────────────────────────────────────────────────────┤
│ 所有任务 phase=blocked（无 done）                            │
│   → 写 .learnings/ERRORS.md（冲刺完全停滞）                  │
│   → 输出到 stderr（触发 --failure-alert 通知）               │
│   → 退出（保留 cron，等人工恢复任务后继续）                   │
├────────────────────────────────────────────────────────┤
│ 有 done 也有 blocked                                         │
│   → 生成冲刺总结（列出 blocked 任务和原因）                  │
│   → openclaw cron remove {cron-id}（自删除）                │
│   → 退出                                                     │
└────────────────────────────────────────────────────────┘

> **task_ref/spawned_at/sprint_branch 清理规则：** phase 从 implementing 进入其他 phase 时，
> 必须清空 task_ref 和 spawned_at（设为空字符串）。仅 spawn 时写入新值。
> sprint_branch 在 done 或 blocked 时清空。
```

### 后台 Agent 执行（sessions_spawn）

implementing phase 的代码编写通过 `sessions_spawn` 启动后台 agent 异步执行：

**Spawn 顺序（关键）：**
1. `sessions_spawn` 启动后台 agent
2. **立即**将 task_ref 和 spawned_at 写入 sprint-plan.md 任务池
3. **立即**将 phase 写入任务池
4. 确认写入成功后，cron turn 才能结束

**Spawn 参数：**
```
sessions_spawn(
  task="执行 spotcat-sprint-dev Implementer Phase。任务: {任务名}。SPRINT_PLAN_PATH={路径} PROJECT_ROOT={路径} TEST_COMMAND={测试命令} from_phase={来源phase} SPRINT_BRANCH={scsprint/xxx} MAX_TEST_PARALLEL=2",
  label="sprint-impl-{任务名}",
  runtime="acp",
  agentId="{agent-id}",
  mode="run"
)
```

**后台 agent 的职责：**
- 读取 sprint-plan.md 获取任务上下文
- 按 implementer-prompt.md 执行：读代码 → 写代码 → 写测试 → 跑测试
- 完成后将交付记录追加到 sprint-plan.md 的 `## 交付记录`

**1.5 小时上限：**
- 每次 spawn 时记录 `spawned_at`（ISO-8601）到任务池
- cron 检查时：如果 `now() - spawned_at > 90min`，视为超时
- 超时处理：cancel 后台任务 → `impl_fail += 1` → 判断是否触发 root-cause

### 持久化计数器

sprint-plan.md 任务池表中维护七个字段：

| 字段 | 含义 | 何时 +1 | 何时重置 |
|------|------|---------|---------|
| `fail_streak` | 连续 quality-review <9 次数 | quality-review < 9 | quality-review ≥ 9 或 root-cause 分析后 |
| `rc_count` | 根因分析执行次数（信息性，不控制流转） | root-cause phase 执行完（写入新值） | 任务 phase 改为 done 时 |
| `impl_fail` | 连续后台 agent 实现失败次数 | 后台 agent 测试不过/超时/失败 | 后台 agent 测试通过时 |
| `task_ref` | 当前后台任务 ID | 每次 spawn 时写入新值 | phase 离开 implementing 时清空 |
| `spawned_at` | 后台任务启动时间（ISO-8601） | 每次 spawn 时写入 | phase 离开 implementing 时清空 |
| `sprint_branch` | Sprint 开发分支名（scsprint/xxx） | pending→implementing 时写入 | done 或 blocked 时清空 |
| `base_branch` | 原始分支名 | pending→implementing 时写入 | done 或 blocked 时清空 |

**终止条件：**
- `fail_streak ≥ 3` → 进入 root-cause
- `impl_fail ≥ 3` → 进入 root-cause
- 任务总轮次 > 10 → 自动进入 root-cause（防振荡）
- root-cause 判定为架构问题或不可修复环境问题 → 任务标记 blocked

## 各 Phase 执行说明

### Implementer Phase
- 职责：编写代码和测试
- 输入：sprint-plan.md 中的任务描述、验收标准
- 输出：代码变更 + 测试通过证明（必须粘贴命令输出）
- 门控：测试必须全绿
- 详细指令见 references/implementer-prompt.md

### Spec Reviewer Phase
- 职责：验证功能对齐验收标准（只评正确性维度，不改代码）
- 输入：任务验收标准 + 实现代码 + 上轮 implementer 测试证据
- 输出：正确性评分 (X/3.0) + 功能偏差列表
- 门控：正确性 ≥ 2.5/3.0
- 详细指令见 references/spec-reviewer-prompt.md

### Quality Reviewer Phase
- 职责：代码质量 + 安全 + 可维护性 + UX 综合评审 + 计算总分
- 输入：实现代码 + Spec Review 的正确性评分
- 输出：综合评分 (X/10) + 各维度得分 + 改进建议
- 门控：总分 ≥ 9/10；安全问题一票否决（总分归零）
- 详细指令见 references/quality-reviewer-prompt.md

## 硬门控 (Hard Gates)

| 门控点 | 条件 | 不通过处理 |
|--------|------|-----------|
| Implementer 完成 | 后台 agent 成功 + 所有测试绿色 | 重新 spawn（impl_fail +1） |
| Implementer 超时 | spawned_at > 1.5h | cancel → impl_fail +1 → 可能 root-cause |
| Implementer 失败 | 后台 agent status=failed/timed_out | impl_fail +1 → 可能 root-cause |
| Implementer 累计失败 | impl_fail ≥ 3 | 进入 root-cause |
| Spec Review 通过 | 正确性 ≥ 2.5/3.0 | phase 设为 implementing，附偏差，重新 spawn |
| Quality Review 通过 | 总分 ≥ 9/10，无安全问题 | merge 到 base_branch，删除 sprint 分支，phase 改为 done |
| Quality Review 安全否决 | 有安全问题 | 总分=0，phase 设为 implementing，重新 spawn |
| 连续 3 轮 Quality < 9 | fail_streak ≥ 3 | 进入 root-cause |
| 根因分析：架构问题/不可修复环境 | 根因类型判定 | phase 改为 blocked |
| 任务总轮次 > 10 | — | 强制进入 root-cause |

## 根因分析协议

连续 3 轮未通过 quality-review，或连续 3 轮 implementer 测试失败时，进入根因分析。本轮内完成，不跨 cron 等待。

根因类型（5 种）：
1. **需求不清** → 更新任务验收标准
2. **任务过大** → 拆分为 2-3 个子任务
3. **技术债务** → 插入清理子任务（不降低评分标准）
4. **架构问题** → 记录到 .learnings/，任务标记 blocked
5. **环境问题** → 验证环境健康，重建测试 fixtures

## 评分标准

**总分 10 分，≥ 9 分过关**

| 维度 | 满分 | 要点 |
|------|------|------|
| 正确性 | 3.0 | 功能完整、API 对齐、无 bug |
| 代码质量 | 2.5 | 类型安全、可读性 |
| 可维护性 | 2.0 | 模块化、文档完整 |
| 测试覆盖 | 1.5 | 单元测试覆盖关键路径 |
| 用户体验 | 1.0 | CLI 输出清晰、错误提示友好 |

**等级:** 9-10 通过 | 7-8 小改 | 5-6 大改 | <5 重做

详细评分细则见 references/scoring.md

## Cron 设置

```bash
openclaw cron add \
  --name "{项目}-sprint" \
  --every 1h \
  --agent {agent-id} \
  --model {model} \
  --timeout-seconds 300 \
  --failure-alert \
  --failure-alert-after 1 \
  --failure-alert-channel feishu \
  --failure-alert-to {群ID} \
  --to chat:{群ID}
```

触发消息模板:
```
SPRINT — 读取 sprint-plan.md，定位最高优先级未完成任务。
implementing phase 通过 sessions_spawn 异步执行，cron 只做调度和状态检查。
reviewing/root-cause 在 cron turn 内同步执行。
门控: 测试绿 → 正确性 ≥2.5 → 总分 ≥9。连续失败触发根因分析。
```

## 学习闭环

每次 phase 失败时，将信息记录到 `.learnings/`：
- 任务名、phase、失败原因
- 根因分析结果（如有）
- 改进建议

## 失败输出格式

```json
{
  "success": false,
  "data": null,
  "error": "描述具体错误原因"
}
```
