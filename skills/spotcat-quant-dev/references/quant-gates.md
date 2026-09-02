# 3-Layer Test Gates

所有 3 层必须通过才能 quality-review PASS。

## 自动化门控（gate-runner）

以下检查已脚本化，不再由 agent 手动判断。quality-review 阶段必须先跑：

```bash
python -m spotcat_gates.gate_runner --config .spotcat/config.yml --run-id <本轮 run_id>
```

结果写在 `.spotcat/runs/<run_id>/gate-output.json`，agent 读这份文件，不自己复述数字或判断是否达标。

已脚本化（不再需要 agent 手动验证，见文件对应 gate 名）：
- `credentials`：凭证扫描
- `position-limit` / `idempotency` / `kill-switch`：P0 行为性测试是否存在且通过——**仅检查指定名字的测试存
  在且通过，不验证该测试是否真的调用了生产策略代码（而非只断言本地字面量）**。测试是否真的构成对真实代码的
  有效验证，仍是人工/LLM 判断，不是脚本判定的对象。
- `date-gap`：数据日期完整性（P1 前置，失败则 backtest-metrics/lookahead-replay 记为 ERROR 并跳过）——**仅
  检查每个日历日期是否存在对应的数据文件，不能、也不会判断文件内容是真实市场数据还是编造/合成数据**。数据
  真实性（非合成）依然是 LLM/人工判断，不在脚本门控范围内。
- `backtest-metrics`：Sharpe/回撤/交易次数/样本内外差距，含 data_hash 校验
- `lookahead-replay`：前瞻偏差位移重放测试
- `code-budget`：单文件行数是否超过 `code_budget.max_file_loc`（`code_budget.ignore_file` 里列出的文件/模式
  除外）。**不属于下面 3 层测试门控**，是独立的代码卫生检查（对应可维护性打分维度），但同样由 gate-runner
  跑出、同样不允许 agent 自己数行数替代。
- `duplicate-symbols`：同一个顶层函数/类名是否出现在多个文件里（测试文件除外）。目标是抓"AI 没查现有代码
  就另起一个文件重新实现"这类问题。**advisory，不计入 overall_status**——FAIL 不会单独阻止进 done，因为存
  在合理假阳性（比如多个模块各自定义同名的 `Config`/`Result` 类不是重复实现）。quality-reviewer 仍必须读
  这份结果，把 FAIL 里列出的每一对文件当证据去判断"是不是真的重复"，计入可维护性(2.0)维度打分，不能因为
  "不计入 overall_status"就当作没看见。

`gate-output.json` 里任一 gate 的 `status` 为 `FAIL` 或 `ERROR` = 本轮不得进入 done，退回 implementing 或
root-cause（`ERROR` 通常意味着脚本本身跑不起来或配置没接好，不是"数字不达标"，应单独记录根因，不要和"数值不
达标"混为一谈）。

## Layer 1: Unit Tests

**目的：** 隔离验证策略逻辑正确性。

**要求：**
- 用已知输入/输出测试策略信号生成
- 测试边缘情况：空数据、单根 bar、极端值
- 测试错误处理路径（坏数据、缺失字段）

**门控：** 所有 unit tests 通过（绿色）。`position-limit`/`idempotency`/`kill-switch` 已脚本化，见上方「自动化门控」。

## Layer 2: Backtest

**目的：** 在真实历史数据上验证策略表现。

**要求：**
- 使用项目文档化数据路径中的真实市场数据运行
- 报告：Sharpe 比率、最大回撤、胜率、交易次数

**门控：** 已脚本化，见上方「自动化门控」（gate: `backtest-metrics`）。

## Layer 3: Data Validation

**目的：** 验证数据日期完整性（按预期日期范围逐日检查文件是否存在）。**不验证数据来源真实性**——数据是否为
真实市场数据（而非合成/编造）没有任何脚本能判断，仍需 LLM/人工判读（见
`quant-quality-reviewer-prompt.md` 的安全规则检查）。

**要求：**
- 数据从项目 CLAUDE.md 中文档化的路径加载
- 数据格式符合预期 schema
- 数据确系真实市场数据，非合成/编造（此项由 LLM/人工判读，非脚本验证）

**门控：** 日期完整性已脚本化，见上方「自动化门控」（gate: `date-gap`）；数据真实性判断不在脚本门控范围内。
