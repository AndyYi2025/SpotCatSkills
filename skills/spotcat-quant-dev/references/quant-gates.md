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
- `position-limit` / `idempotency` / `kill-switch`：P0 行为性测试是否存在且通过
- `date-gap`：数据日期完整性（P1 前置，失败则 backtest-metrics/lookahead-replay 记为 ERROR 并跳过）
- `backtest-metrics`：Sharpe/回撤/交易次数/样本内外差距，含 data_hash 校验
- `lookahead-replay`：前瞻偏差位移重放测试

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

**目的：** 验证数据完整性和来源。

**要求：**
- 数据从项目 CLAUDE.md 中文档化的路径加载
- 数据格式符合预期 schema

**门控：** 已脚本化，见上方「自动化门控」（gate: `date-gap`）。
