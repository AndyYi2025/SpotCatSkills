# SpotCatSkills 量化开发基础设施重新设计

- 状态：draft，待与 codex(spotcat-e4) 独立方案对齐
- 作者：Claude (botapp-c0，跨会话协作 spotcat-e4)
- 日期：2026-08-25
- 参考：D:\codebase\megaview\Botapp（omnimay，AI 销售助手项目）的治理机制

## 1. 问题

SpotCat 是给多个量化项目复用的 skill 插件（sprint-dev 通用 SDD / quant-dev 量化 SDD / quant-research
研究循环）。当前定位模糊导致三个具体问题：

1. **纯 prompt，无执行层**：`quant-gates.md`/`safety-rules.md`/`quant-scoring.md` 里的检查项全部是让 agent
   "自己检查"，没有一行可执行代码验证。QUALITY-GATES-006（megaview RFC）명确指出这类问题的通病：agent 的自述
   不能作为证据，尤其在全 Cron 驱动、无人盯每一轮的场景下，agent 完全可能读错、编造或选择性汇报。
2. **多项目复用无治理**：用户一人在多个量化项目里用 SpotCat，尚无正式依赖机制，shared 规则一旦演化，旧项目
   会不会被悄悄破坏、新规则怎么安全推广，都没有答案。
3. **README/plugin.json 的运行时描述（OpenClaw/ACP）是过时占位**，与实际情况脱节，需要在落地时一并澄清（不
   在本次实现范围，仅记录）。

## 2. 目标

- 把 SpotCat 从"纯 prompt 集合"升级为 **prompt + 可执行 gate 脚本 + 契约 schema** 三层结构，让规则对 agent
  真正有约束力，而不是指望自觉。
- 建立多项目复用时的分发/版本治理，但不过度设计——用户是 solo 场景，不需要团队级 RFC 审批。
- 给出可以直接复用的 megaview 实现细节（脚本算法、fixture 测试模式、文档模板），减少重新发明。

## 3. 总体架构

```
Skill 层（现有，仅需微调）
  SKILL.md + references/*.md —— 编排流程、留给 LLM 的语义判断

Gate 脚本层（新增）
  shared/scripts/ —— 框架无关的机械检查脚本，统一 JSON 输出协议
  shared/scripts/gate-runner.py —— 单入口，跑全部 gate，聚合输出

契约 Schema 层（新增）
  shared/schemas/backtest-result.schema.json —— 规范化"回测结果"格式
  跨框架关键解法：SpotCat 不认识任何量化框架（vnpy/nautilus_trader/custom），
  只认这份 schema；每个消费项目自己写一次性 adapter 把框架原生输出转换成规范 json

项目配置层（新增，每个消费项目自己维护，不进 SpotCat 仓库）
  .spotcat/config.yml —— 路径/命令/阈值
  .spotcat/adapters/ —— 该项目框架特定的结果转换 adapter（一次性成本）
```

Skill 层的 prompt 职责从"agent 自己判断/检查"改为"agent 跑 `gate-runner.py`，读它吐出的结构化 JSON 做综合"。

## 4. 检查项三分类

逐条来自对 `quant-gates.md`/`safety-rules.md`/`quant-scoring.md`/`quant-spec-reviewer-prompt.md`/
`quant-root-cause-analysis.md` 的实读盘点（spotcat-e4 核实，行号以其读取时的文件版本为准，落地时需重新核对）。

### 4.1 可 100% 脚本化

| 检查项 | 脚本设计要点 |
|---|---|
| 硬编码凭证/API key | secret scanner（正则/熵检测，或直接用 gitleaks） |
| bare `except` | `ruff check --select E722,BLE001` |
| 公共函数缺类型提示 | `mypy --disallow-untyped-defs` 或 AST 扫 |
| 硬编码绝对路径 | regex/AST 扫字符串字面量是否匹配路径模式 |
| 数据路径/日期完整性 | 脚本读 config 的 `data_root`，`glob` 实际文件，跟声明日期区间做差集 |
| 数据是否合成 | 强启发式：统计特征检测（价格过度平滑/成交量分布异常等合成数据指纹） |
| **回测指标提取**（Sharpe/回撤/胜率/交易次数） | 全设计里最关键一条，直接对应 QUALITY-GATES-006 证据等级A：脚本读规范 json，PASS/FAIL 由脚本判，agent 只读结果，不自己"报告" |
| 样本内/样本外差距 >阈值 | 同一次回测结构化输出里取 `in_sample_sharpe`/`out_sample_sharpe` 算差值百分比，纯算术 |
| 策略默认 paper 模式 | 脚本读策略入口默认配置值，检查等于 `"paper"` |
| 代码行数/文件预算 | 移植 megaview `check-code-budget.sh` 算法（见 §6），只卡 SDD 的 quality-review 阶段，quant-research 探索期不卡 |
| 测试覆盖率 | `pytest-cov`/`coverage.py` 直接出数字 |

### 4.2 脚本打底 + LLM 语义判断叠加

| 检查项 | 混合方案 |
|---|---|
| 前瞻偏差 | **位移重放测试**：信号函数分别喂 `data[:T]` 和 `data[:T+k]`，断言 T 处输出逐位相同，抓大多数"用了未来数据"的真实 bug；更隐蔽的"时点可得性"问题（如用当天收盘价却在收盘前决策）重放测试无法暴露，留给 LLM 读代码 |
| 仓位限制真的写进代码 | **不用存在性扫描**（`grep`/AST 找相关函数会有假阳性——import 了但从没调用照样过）。改成**行为性测试**：要求一条命名规范化测试（如 `test_position_limit_enforced`）用具体断言（`assert placed_qty <= max_position`）跑通，脚本只检查该测试存在且通过 |
| paper/live 路径漂移 | 脚本做 AST/import-graph diff，确认 paper 和 live 两个入口最终指向同一个信号生成函数对象；diff 出真实分叉时交给 LLM 判断"是否有意为之"（如 live 多了风控包装） |
| 硬编码参数应放 config（魔法数字） | 脚本启发式扫描（数值字面量非来自 config/常量），列候选，LLM 判断哪些该外部化 |
| "无显式启用不能自动交易" | 强制下单调用收敛到唯一入口函数，脚本 AST 检查该入口函数体第一行是 `live_enabled` 检查；异常写法交给 LLM 复核 |

### 4.3 只能留给 LLM

- 策略逻辑是否正确实现（对齐验收标准的语义判断）
- 架构可维护性（策略逻辑/数据加载/执行是否清晰分离）
- 代码风格是否符合项目既有习惯（格式化部分可 `ruff format --check` 脚本化，"是否符合习惯"仍需读代码）
- root-cause 7 种根因中"需求不清/任务过大/架构问题/环境问题"4 种——判断"为什么失败"本身没法脚本化

## 5. 契约 Schema：`shared/schemas/backtest-result.schema.json`

字段：`sharpe_ratio` / `max_drawdown` / `win_rate` / `trade_count` / `profit_factor` /
`in_sample_sharpe` / `out_sample_sharpe` / `lookahead_check` / **`data_hash`**（回测用到的数据文件 hash，
写入结果——顺带解决"历史数据源被静默修改导致回测不可复现"这个问题，不用单独开发）。

`backtest_command`（`.spotcat/config.yml` 里定义）的约定是：跑完必须把结果写成这份 schema 的 json。具体怎
么从 vnpy/nautilus_trader 原生输出转换，由每个项目自己写一次性 adapter，不是每个 sprint 都要写。SpotCat 的
gate 脚本永远只读这份规范 json，不需要认识任何具体框架。

## 6. 统一 gate 输出协议

所有 gate 脚本吐同一格式 stdout：

```json
{"gate": "backtest-metrics", "pass": true, "evidence_tier": "A", "details": {"sharpe_ratio": 1.34, "max_drawdown": 0.11}}
```

`gate`/`pass`/`evidence_tier`/`details` 四字段是 QUALITY-GATES-006 证据分级四要素（业务不变量/证据等级
A-B-C/执行环境/证据状态）的机器版本。`quality-reviewer-prompt.md` 改为：agent 跑
`.spotcat/scripts/gate-runner.py --config .spotcat/config.yml` 一次性拿到全部 gate 结果 → 读 JSON 填评审
模板，角色从"自己判断"变成"读真实证据做综合"。

## 7. 项目配置层：`.spotcat/config.yml`

```yaml
version: 1
paths:
  data_root: D:/quantdata/markets/CNFUT/
  data_format: parquet
  expected_date_range: { start: "2018-01-01", end: auto }
commands:
  test: "pytest tests/ -v --json-report --json-report-file=.spotcat/last-test-result.json"
  backtest: "python -m backtest.run --strategy {strategy} --output .spotcat/last-backtest-result.json"
thresholds:
  min_sharpe: 1.0
  max_drawdown: 0.15
  min_trades: 30
  max_oos_is_gap_pct: 50
code_budget:
  max_file_loc: 500   # 落地时二选一：沿用 megaview 当前脚本值 800，还是收紧到文档值 500——不要凭空定第三个数字
  ignore_file: .codebudgetignore
safety:
  paper_only: true
  live_enable_flag_path: .spotcat/LIVE_ENABLED
```

## 8. 分发/版本治理（两阶段，避免过早负重）

仓库现在 0.1.0、7 commit，无人真正 pin 过旧版本——还没有"改动会破坏谁"这个对象。

### Phase 0（现在，直接改，不背版本纪律）

落地 §4-§7 全部内容（六项加固 + 脚本层 + schema + config），**不需要 CHANGELOG**——第一批变更记录的是
"没人用过的东西的修改史"，没有意义。改动直接改，改完在至少一个真实 sprint 上跑一轮验证（canary）。

### Phase 1（Phase 0 落地 + 至少一次真实 sprint 验证通过后）

- 打 tag `v1.0.0` 作为基线，从此刻起才要求 CHANGELOG。
- **版本纪律的契约边界 = 整个仓库**（不只是 `shared/`）：因为分发机制是钉整仓库单一 semver
  （`plugin.json`），`skills/*/references/*.md` 的改动跟 `shared/` 改动一样会 breaking 下游，不能绕开。唯一
  例外是 `quant-context.md` 实例化后回填到各项目自己 CLAUDE.md 的具体字段值——那些从不写回本仓库。
- "要不要写 changelog/走 canary"（版本纪律轴）和"要不要进 `shared/` 供跨 skill 复用"（准入标准轴，类比
  megaview `packages/ui`：至少两个项目用得上 + 不依赖项目特定假设）是两条独立判断，不要混。
- 分发机制：**git submodule 钉版本 + `plugin.json` semver + 新增 `CHANGELOG.md`**（不依赖 OpenClaw 或任何
  agent 运行时——用户确认不用 OpenClaw，README 的 OpenClaw/ACP 描述是过时占位）。升级流程：读 CHANGELOG
  since last pin → 决定是否 bump → 单个真实 sprint canary 验证 → 推广到其他项目。
- CHANGELOG 条目格式参考 megaview 轻量 ADR（一页纸：决策/背景/后果/替代方案），比自由格式更有结构，又比
  正式 RFC 轻得多。

## 9. 明确不做的

- 正式 RFC 审批流程（无其他 reviewer，solo 场景用不上）
- Cell grid 单元格网格（规模远没到位）
- 架构文档真源分级 + drift-scan cron（没有 RFC/ADR 体系，规模不够）
- 四档棘轮光谱完整版（hard/ratchet/approveable exemption/metric only）——只需要 **ratchet**（代码预算）和
  **hard**（safety veto）两档；**量化 safety 规则永远 hard veto，不能棘轮**（不能因为存量策略都没做仓位限
  制就默许新策略也不做）

## 10. 可直接复用的 megaview 实现（落地时的具体参考，非重新设计）

1. **`scripts/check-code-budget.sh` + `_check-code-budget.mjs` 算法** → 移植到
   `shared/scripts/code_budget.py`。三条防滥用规则必须原样搬：拒绝 `.codebudgetignore` 裸通配、拒绝覆盖
   整个扫描根、拒绝 ignore 清空所有候选文件后仍报全绿。全程 **fail-closed**（缺源/不可读/baseline 损坏/
   扫描根不存在 → 非 0 退出，不静默放行）。baseline JSON 字段形状（`schemaVersion`/`scope`/
   `fileViolations`/`features`/`_meta`）原样复用；棘轮收紧走专门的 `--update-baseline` 命令，不手改 JSON。
2. **`scripts/check-code-budget.test.sh` 的 fixture 测试模式** → 每个新 gate 脚本都要配。用临时目录 +
   合成文件断言退出码，覆盖正常路径（全绿/新增违规/增长）和防御路径（ignore 滥用/baseline 损坏/源目录
   缺失）——治理脚本本身也要有测试，不能只凭"看着对"上线。
3. **QUALITY-GATES-006 的 JSON 证据字段** → §6 gate 输出协议的原型，字段名基本对着抄
   （`status`→`pass`，`evidenceLevel`→`evidence_tier`）。
4. **`mgv-mr-review` 的效率流程文本**（带时间预算的步骤表 + 5 条原则）→ 整段风格化搬进
   `quant-quality-reviewer-prompt.md`，"harness/port"替换成"safety-rules/仓位限制"，原则本身不用改。
5. **`docs/code-budget.md` 的 FAQ 文档模板** → 直接套用写 `shared/code-budget.md`：阈值表、棘轮契约、
   日常命令、重生 baseline 流程、例外机制、触发层、FAQ。

## 11. 验收标准

- [ ] `shared/scripts/` 下每个 gate 脚本都有对应 fixture 测试，覆盖正常 + 防御路径
- [ ] `gate-runner.py --config .spotcat/config.yml` 单次运行输出全部 gate 的统一 JSON
- [ ] `backtest-result.schema.json` 定稿，至少一个真实项目写出 adapter 并跑通
- [ ] `quant-quality-reviewer-prompt.md` 改为读 gate JSON 而非自行判断；safety veto 提前到评分之前
      （对齐 sprint-dev 现有顺序）
- [ ] `shared/code-budget.md` 落地，LOC 阈值只定一个数字（不产生第三个）
- [ ] 至少一次真实 sprint 完整跑通 Phase 0 全部改动，作为 v1.0.0 canary 证据
- [ ] `CHANGELOG.md` 从 v1.0.0 起启用，此前改动不需要补记

## 12. 风险

| 风险 | 缓解 |
|---|---|
| 脚本层引入后 agent 绕过脚本、自己编结果 | prompt 明确要求"必须贴 gate-runner 原始输出"，quality-review 阶段人工抽查真实性 |
| 跨框架 adapter 一次性成本被低估，每个项目实际要反复改 | 先在一个真实项目上验证 adapter 稳定后再推广，不是全部项目并行起步 |
| LOC 阈值/config 字段设计过度超前于实际用量 | Phase 0 只做当前六项 + 已验证有用的脚本，不为假设中的未来项目类型预建字段 |
| 版本纪律在 Phase 1 启动后增加维护负担 | 严格按"契约边界=整仓库"执行，但 changelog 写作成本很低（一页纸 ADR 格式），非阻塞性 |
