# SpotCatSkills 量化开发基础设施重新设计（合并终版 · 二次复核后修订）

- 状态：已收敛并完成二次复核——合并 botapp-c0 初稿 + spotcat-e4 独立方案，spotcat-e4 复核合并稿后指出 1 处
  硬伤（§11 输出捕获缓解措施与全文原则矛盾）+ 2 处需澄清（§6.1 LOC 阈值歧义、P1/P2 日期缺口归属），已修订
- 输入：本文档前身草稿（同目录）+ `2026-08-25-quant-dev-infra-redesign-design-codex.md`（spotcat-e4 独立产出）
- 日期：2026-08-25（初稿）/ 2026-08-26（复核修订）
- 参考：D:\codebase\megaview\Botapp（omnimay）的治理机制

## 0. 出发点

用户的真实场景：**一个人，多个量化项目，用 SpotCat 的 skill 定义驱动 Cron-based agent 自动开发**。SpotCat
现在 100% 是 markdown prompt，没有一行可执行代码——所有"检查"最终退化成"agent 说它检查过了"。这在无人值
守、7×24 跑 Cron 的场景下是致命的：没有人实时盯着每一轮 quality-review 的结论是不是编的（QUALITY-GATES-006
问题的量化版本）。

**组织原则**：不按"SDD 哪个 phase"或"哪些好脚本化"分组，而按**出错代价（blast radius）**排优先级——脚本
化容易的东西不一定该优先做（"函数有没有类型提示"极易脚本化但出错代价趋近于零；"仓位限制是否真的生效"较难
脚本化但出错代价是真实亏钱）。无人值守场景下，优先钉死代价最高的环节。

## 1. 优先级分层与落地顺序

| 层级 | 内容 | 出错代价 |
|---|---|---|
| P0 | 资金安全硬门（kill switch、仓位限制、凭证、防重复下单） | 真实亏钱/失控交易 |
| P1 | 回测证据完整性（脚本解析真实数字，而非 agent 自述；**含日期缺口/schema 前置校验**，见 §3） | 全部下游判断建立在假数据上 |
| P2 | 长期防漂移/审计（data hash、前瞻偏差重放测试——不影响"这次数字对不对"，只影响"未来能否复现"） | 数字会随时间漂移或被静默污染 |
| P3 | 多项目分发与配置层 | 效率/维护成本，不影响正确性 |
| P4 | 代码/流程卫生（LOC 预算、PARTIAL 记录、prompt 顺序） | 返工成本，不影响正确性或安全 |

> **排序轴的澄清**（spotcat-e4 复核指出的分歧）：P0-P4 是"出错代价"排序，不是严格的"先跑完这层才跑下一
> 层"执行顺序。日期缺口校验按代价属于"数据完整性"问题，但按**执行依赖**必须先于 P1 的指标解析（数据有缺口
> 时算出来的 Sharpe 从一开始就是错的），因此它是 P1 gate-runner 流程里的前置步骤，不是 P2 阶段做完 P1 才
> 补的动作。P2 剩下的两条（data_hash、位移重放测试）跟 P1 之间才是真正的独立关系，不互相依赖执行顺序。

```
P0 → P1（含日期缺口前置校验）→ P2（先在一个试点项目里跑通全部，完成至少一次真实 sprint 的 canary 验证）
  → P3（多项目分发；CHANGELOG 纪律从这里正式启动——P0-P2 阶段不背这个负担，因为还没有第二个消费者）
  → P4（可与 P3 并行，互不阻塞）
```

**"多项目复用"虽是触发这次重新设计的直接诉求，但排在最后**：先证明单个项目的门控是真的，再谈复制到 N 个
项目——顺序反过来，等于把一个可能有假绿漏洞的机制原样复制 N 份。

## 2. P0：资金安全硬门

判断标准不是"能不能脚本化"（其实都能），而是"允不允许有任何 advisory 残留"。P0 任何一条都不能是"建议
agent 检查"，必须是脚本 exit code 决定，agent 无法覆盖。

### 2.1 现状

`shared/safety-rules.md` 7 条规则全部是 prose，强制手段是"quality-review 阶段 agent 检查，违反则总分=0
veto"——veto 计算本身是真的，但"有没有违反"这个判断目前 100% 靠 agent 读代码得出，是唯一的信任支点，也是
最薄弱环节。`quant-quality-reviewer-prompt.md` 当前执行顺序（读文件→3层门控→打分→安全检查veto→算总分）
把安全检查排在倒数第二步，比通用版 `spotcat-sprint-dev/references/quality-reviewer-prompt.md`（安全检查
是 step 2，最先执行）更弱——量化场景理应更严格，现状反而更松。

### 2.2 设计

**仓位限制：存在性改成行为性契约。** 不接受"扫代码里有没有限仓字符串"（`import position_limit_check` 但
从不调用照样通过）。改为：strategy 代码必须提供命名规范化测试（如 `test_position_limit_enforced`），含具体
数值断言（`assert placed_qty <= max_position`），脚本只检查「测试存在 + 通过」。缺失或不过 = P0 硬失败，
无条件退回 implementing，不计入正常的容错重试轮次。

**双层 kill switch。** 项目级（`.spotcat/config.yml` 的 `live_enable_flag_path`）之外，加一个仓库外的**全
局开关**（如 `~/.spotcat/GLOBAL_LIVE_ENABLE` 或环境变量）。live 交易必须"全局 AND 项目"同时为真才放行。
理由：单项目 flag 模型下用户只要有一个项目忘记复位就可能出问题；全局开关是"一人管多项目"场景特有的总闸，
出事时拉一个开关即可让所有项目同时停止 live 交易。

**防重复下单（幂等性）——之前完全没覆盖的真实缺口。** Cron 驱动、implementing 阶段异步 spawn（最长1.5h），
某轮执行中途崩溃/超时/被杀，下一轮重试有没有机制保证不对同一信号重复下单？7 条 safety-rules 里没有这条。
新增规则：每个信号/订单必须带幂等 key（如 `{strategy_id}_{signal_timestamp}_{side}`），下单前查询是否已有
相同 key 的记录，有则跳过；这是下单执行路径里的强制代码逻辑，要有行为性测试
（`test_duplicate_signal_not_double_ordered`）。

**凭证扫描。** `safety-rules.md` L9 已有规则但落地靠 agent 判断，改为脚本：secret scanner（gitleaks 或等价
正则/熵检测）跑在 diff 上，P0 级 veto。

**fail-closed，不做默认值。** 任何 P0 相关配置字段（仓位上限、live_enable 开关路径、幂等 key 格式）在
`.spotcat/config.yml` 里缺失时，脚本必须拒绝运行并报错，不能静默用"安全默认值"顶上——"没配置就当最保守"这
个逻辑本身也是一段可能写错的代码，缺失配置应显式失败，逼用户去补。

## 3. P1：回测证据完整性

解决 QUALITY-GATES-006 的量化版：**"agent 报告 Sharpe=1.34" 本身不是证据，除非能证明这个数字来自脚本对真
实回测输出的解析，而不是 agent 读了一眼输出文件之后口算/编造**。

- 每个项目的 `backtest_command` 必须产出符合规范 schema 的 JSON（`shared/schemas/backtest-result.schema.json`：
  `sharpe_ratio` / `max_drawdown` / `win_rate` / `trade_count` / `profit_factor` / `in_sample_sharpe` /
  `out_sample_sharpe` / `lookahead_check` / `data_hash` / `generated_at`）。
- 不同框架（nautilus_trader/vnpy/custom）原生输出各不相同，靠**每个项目自己写一次性 adapter** 转换成规范
  JSON。SpotCat 的 gate 脚本永远只认这份 schema，不需要认识任何具体框架。
- 统一 stdout 协议：`{"gate": "...", "pass": bool, "evidence_tier": "A|B|C", "details": {...}}`。
  `quality-reviewer-prompt.md` 改为"跑 gate-runner，读 JSON 填表"，而非自行判断。

**为什么排在 P0 之后、P2/P3 之前**：P1 是其余所有量化质量判断的地基——3 层测试门控、过拟合检测、
spec-review 的"正确性"打分，全都间接依赖"这个 Sharpe/回撤数字是真的"这个前提。P1 不落地前，讨论"要不要给
N 个项目做统一版本管理"没有意义——会把假绿 machinery 版本化分发到 N 个项目。

**谁测试这些脚本**：把检查从 prompt 移到脚本，没有消灭"验证者本身可能出错"的问题，只是把它从"agent 会不
会说谎"搬到了"脚本会不会有隐藏 bug"，且**脚本 bug 更隐蔽**——没人会像质疑 agent 结论那样怀疑一段跑通很多
次的解析代码。一旦 `parse_backtest_output()` 有边界 bug（比如框架版本升级后字段名变了，脚本悄悄解析出 0 却
被判定为"低于阈值正常 FAIL"），会在所有项目所有轮次里静默产生错误判断，比单次 agent 自述错误影响面更大。
**对策**：gate 脚本本身要有单元测试（喂已知的合成/历史真实输出，断言解析出的数字符合预期）；**"解析失败"
和"指标真实低于阈值"必须是两种不同的退出码/状态**，不能把 parse error 归并成"gate FAIL"，那样等于把工具
bug 伪装成了业务失败，反而更难发现。

**输出必须由 Cron harness 独立捕获，不经过 agent 转述。**（spotcat-e4 复核发现的漏洞，纠正 §11 原稿）
`gate-runner.py` 的 stdout/stderr 必须由触发它的 Cron harness 进程直接落盘存档（子进程输出重定向到
`.spotcat/runs/<run_id>/gate-output.json`），而不是"要求 agent 在 review 里贴出来"。理由：一旦信任链条里
有"agent 愿不愿意贴真实输出"这一环，就退回了自述模型，和 P0/P1 全篇"agent 无法覆盖脚本判定"的原则矛盾；
而且实际运行是无人值守 7×24 Cron，压根没有人在场做"人工抽查"这个动作，指望人工核实在这个场景下等于没有
缓解。`quality-reviewer-prompt.md` 读的是 harness 落盘的这份文件，不是 agent 自己转述的内容。

**日期缺口/schema 校验是 P1 的前置步骤，不是独立阶段。**（spotcat-e4 复核发现：按"出错代价"分级和按"执行
依赖顺序"排列是两条不同的轴，这一项如果按代价分进 P2，会漏掉它是 P1 输入前提这个事实）数据本身有日期缺口
时，P1 脚本算出来的 Sharpe/回撤数字从一开始就是错的——不能先跑完 P1 的指标解析，再靠"后面 P2 阶段"才发现
数据不完整。因此该校验是 `gate-runner.py` 在 P1 流程里的**前置校验**：跑在 backtest-metrics 解析之前，校
验不过直接短路退出，不进入指标解析。§9 验收标准与流程图据此调整（见下）。

## 4. P2：可复现性/长期防漂移（不是执行阶段，是审计性质，跟 P1 并列而非顺序依赖）

P2 只保留两条真正独立于"这一次数字对不对"、只影响"未来能不能复现/会不会被污染"的检查：

**前瞻偏差：位移重放测试。** 信号函数分别喂 `data[:T]` 和 `data[:T+k]`，断言 T 处输出逐位相同，抓住"代码
里直接用了未来数据"的大多数真实 bug。抓不住"数据在 T 时刻是否真的已披露"这类时点可得性问题（重放测试本
身是确定性的），这部分留给 LLM 读代码。**归类为 P2 而非 P1**：P1 解决"这次数字有没有造假"，P2 解决"这个
数字长期会不会漂移/被污染"，两者是不同层面的问题。

**历史数据不可变性：`data_hash`。** schema 里带 `data_hash` 字段，脚本对本次用到的数据文件区间算 hash 写
进结果——不是为了当次门控用，是为了未来审计：某天回测结果对不上，第一件要排除的事是"数据源是不是被静默
改过"（数据商重新调整了某天价格、修 bug、静默补缺失数据），没有 hash 记录这个问题永远无法确认。

## 5. P3：多项目分发与配置层

### 5.1 契约范围

`plugin.json` 给整个仓库定版本号，consuming project 整体 pin 一个版本，不是分别 pin `shared/` 和某个 skill
子目录。判定范围 = **整个仓库**，除了 `quant-context.md` 类模板文件被各项目实例化后回填到自己
`CLAUDE.md`/`.spotcat/config.yml` 的具体字段值（从不回写本仓库）。不明确这点，后续改
`skills/spotcat-quant-dev/references/*.md` 或新增 `shared/scripts/*` 时会有人误以为"不在 shared/ 里就不算
breaking change"，绕开该走的版本纪律。

### 5.2 分发机制：vendor 同步，不用 git submodule

**已推翻的原方案**：git submodule + 手动 bump。推翻理由——submodule 假设"钉版本的操作有人在场审查"，但
SpotCat 的实际运行模型是 **Cron 驱动的自主 agent 在做 git 操作**（implementing 阶段 agent 自己 commit）。
这个模型下 submodule 有两个具体风险：① agent 在 consuming project 里做 `git add -A && git commit` 时若不
清楚 submodule 语义，容易只提交"指针脏了"的状态（detached HEAD 上有本地改动但没提交/没推），下次
`git submodule update` 直接静默丢弃这些改动且无明显报错——这是要过几周才会被发现的静默数据丢失。②
`git submodule update --remote` 本身需要一次显式决策，如果这个决策也被 Cron 自动做了，等于把"要不要升级
SpotCat 版本"也自动化了，恰恰违背"升级必须读 CHANGELOG + 走 canary"的设计初衷。

**采用方案**：consuming project 根目录放 `.spotcat-version`（内容是 SpotCat 仓库的 commit SHA 或 tag），
配一个 `spotcat sync` 脚本（浅 clone/checkout 或 `git archive` 导出对应版本文件树，覆盖到
`.spotcat/vendor/`）。`.spotcat/vendor/` **不是嵌套 git 仓库**——升级永远是显式动作
（`spotcat sync --to v1.2.0`），不会被 Cron 自动触发；vendor 目录内容变化像普通文件改动一样被正常 commit
记录，出问题可见、可 diff、可 revert。代价是失去 submodule 自带的"这是外部依赖"语义标记，用
`.spotcat-version` 文件 + `.gitattributes` 标记 vendor 目录为 generated 内容弥补，成本远低于 submodule 在
自主 agent 操作下的风险。

升级流程不变：读 CHANGELOG since last pin → 决定是否 sync → 单个真实 sprint canary 验证 → 推广到其他项目。
CHANGELOG 条目格式参考 megaview 轻量 ADR（一页纸：决策/背景/后果/替代方案）。

### 5.3 `.spotcat/config.yml`

```yaml
version: 1
spotcat_schema_version: 1   # config 自身也版本化，见下方
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
  max_file_loc: 500   # 落地时二选一，不产生第三个数字，见 §6.1
  ignore_file: .codebudgetignore
safety:
  paper_only: true
  live_enable_flag_path: .spotcat/LIVE_ENABLED
  global_kill_switch: "~/.spotcat/GLOBAL_LIVE_ENABLE"
  idempotency_key_format: "{strategy_id}_{signal_timestamp}_{side}"
```

两条原则：**schema 校验先于任何 gate 运行**——gate-runner 启动时先校验 config 是否符合 JSON schema，字段
缺失/类型错误直接拒绝执行，尤其 P0/P1 相关字段不允许"缺字段就用默认值"这种静默降级（呼应 §2.2 fail-closed）。
**config 本身也要版本化**——`spotcat_schema_version` 字段，gate-runner 拒绝运行版本不匹配的 config（提示需
要跑迁移脚本），避免"SpotCat 仓库升级了 schema，但某个项目的 config 还是老格式，脚本安静地用旧字段名读出
undefined"这种漂移。

### 5.4 落地顺序

先在**一个**真实项目里把 P0-P2 的脚本层跑通、完成至少一次真实 sprint 的 canary，再谈"怎么让另外 N 个项目
复用同一套东西"的分发机制。分发机制解决的是"怎么复制"，如果被复制的东西本身没验证过，分发机制做得再好
也只是把问题复制了 N 份。

## 6. P4：代码/流程卫生

改动全部是"改进现有 markdown 内容"，出错代价最低，可与 §5 并行、互不阻塞。

### 6.1 LOC 预算

`skills/spotcat-sprint-dev/references/quality-reviewer-prompt.md` 已有一条**软性**"文件 < 800 行"检查项
（"代码质量"维度的扣分项，非硬否决），`scoring.md` 的"可维护性"维度又有一次模糊提到"单体文件过长"。若新
LOC 棘轮直接塞进 `quant-gates.md`，会出现三套并存标准。

**已核实（2026-08-26）：megaview 自己这个数字就存在真实的文档/代码不同步**——`scripts/_check-code-budget.mjs`
里 `LINES_HARD = 800`，这是 CI 和本地 pre-push **实际强制生效**的值；但 `docs/code-budget.md` 和 ADR
`governance-095` 都写"单文件上限 500 行"，是 DX-002 的目标值，**并未真正落地到脚本里**。也就是说 megaview
自己的文档正是"advisory 会漂移、脚本才是事实"这条道理的反例——不能引用它的文档数字当作"megaview 用的是
500"，实际在跑的是 800。**方案**：新建 `shared/code-budget.md`，两个 SDD skill 都引用它，统一一个数字
（用户拍板：维持接近现有 sprint-dev 的 800，还是收紧到 500——不要凭空产生第三个数字，也不要照搬 megaview
文档里没有真正生效的 500），删掉旧软性检查项，改成引用新文件的脚本硬否决——移植 megaview
`check-code-budget.sh` 算法（baseline 棘轮只减不增、`.codebudgetignore` 三条防滥用规则、fail-closed）。
**只卡 SDD 的 quality-review 阶段，不卡 quant-research 的 prototyping/backtesting 阶段**——研究原型允许
先写乱，进 sprint 才收紧。

### 6.2 安全检查顺序前移

`quant-quality-reviewer-prompt.md` 顺序改为"读文件→安全规则/P0门控→3层门控→打分→算总分"，对齐
`spotcat-sprint-dev` 已在用的顺序。改动小（挪几行），意义是把最贵的错误挪到最先检查，避免 agent 在注定要
被 veto 的改动上浪费打分力气。

### 6.3 PARTIAL/NOT_DONE 强制记录

`skills/spotcat-quant-dev/assets/quant-sprint-plan-template.md` 的"评分记录"/"交付记录"表格没有强制字段
要求"这一轮实际有没有做完"。加必填字段（"结果"列从 `PASS/RETRY` 扩展为 `PASS/RETRY/PARTIAL/NOT_DONE` 四选
一，`PARTIAL`/`NOT_DONE` 必须附一句话原因），给 root-cause-analysis 阶段留可读历史，不靠猜。

## 7. 明确不做的事（现阶段）

- 正式 RFC 审批流程——solo 场景，没有需要说服的第二个人，CHANGELOG + rationale 已够
- Cell grid 单元格网格——SpotCat 3 个 skill 的量级完全用不上
- 架构文档真源分级 + drift-scan cron——只有一份 `docs/architecture.md`，没有多文档互相冲突的问题要解决
- 四档棘轮光谱完整版——只需要 hard 和 ratchet 两档；**量化 safety 规则必须永远 hard veto，不能因为存量策
  略都没做仓位限制就放行新策略**
- git submodule（见 §5.2，已裁定改用 vendor 同步）

## 8. 可直接复用的 megaview 实现

1. **`scripts/check-code-budget.sh` + `_check-code-budget.mjs` 算法** → 移植到
   `shared/scripts/code_budget.py`。三条防滥用规则原样搬：拒绝 `.codebudgetignore` 裸通配、拒绝覆盖整个
   扫描根、拒绝 ignore 清空所有候选文件后仍报全绿。全程 fail-closed。baseline JSON 字段形状
   （`schemaVersion`/`scope`/`fileViolations`/`features`/`_meta`）原样复用；棘轮收紧走专门的
   `--update-baseline` 命令。
2. **`check-code-budget.test.sh` 的 fixture 测试模式** → 每个新 gate 脚本都要配，覆盖正常路径 + 防御路径
   （§3 已扩展：还要覆盖"解析失败"这个独立于"阈值未达标"的状态）。
3. **QUALITY-GATES-006 的 JSON 证据字段** → §3 gate 输出协议的原型，字段名基本对着抄。
4. **`mgv-mr-review` 的效率流程文本**（带时间预算的步骤表 + 5 条原则）→ 整段风格化搬进
   `quant-quality-reviewer-prompt.md`。
5. **`docs/code-budget.md` 的 FAQ 文档模板** → 直接套用写 `shared/code-budget.md`。

## 9. 验收标准

- [ ] P0：仓位限制/kill switch(双层)/幂等下单/凭证扫描全部为脚本硬否决，无 advisory 残留；配置缺失 fail-closed
- [ ] P1：`gate-runner.py` 单次运行输出全部 gate 的统一 JSON，且 JSON 由 Cron harness 独立落盘捕获（不经
      agent 转述）；`backtest-result.schema.json` 定稿，至少一个真实项目写出 adapter 并跑通；解析失败与阈值
      未达标为两种不同状态；**日期缺口/schema 前置校验跑在指标解析之前，不过即短路**
- [ ] P2：位移重放测试 + `data_hash` 落地（审计/长期防漂移，跟 P1 并行验证，不是 P1 做完才开始）
- [ ] 以上两层在同一试点项目完整跑通至少一次真实 sprint 的 canary 验证
- [ ] P3：`.spotcat-version` + `spotcat sync` 脚本可用；config schema 版本化校验生效；CHANGELOG 从此刻启用
- [ ] P4：LOC 阈值统一为一个数字；`quant-quality-reviewer-prompt.md` 安全检查顺序前移；sprint plan 模板
      PARTIAL/NOT_DONE 字段生效

## 10. 留给用户拍板的问题

1. **LOC 预算最终数字**：维持接近现有 sprint-dev 的 800，还是收紧到 500？两个 skill 需要统一成一个数字。
2. **全局 kill switch 用什么形式**：本机文件、环境变量，还是要考虑跨机器同步（同一人用多台机器跑不同项目
   的 Cron）？
3. vendor 同步方案（§5.2）是否认可？（本方案已裁定推荐此方案而非 submodule，除非有未列出的强诉求）

## 11. 风险

| 风险 | 缓解 |
|---|---|
| 脚本层引入后 agent 绕过脚本、自己编结果 | **不依赖 agent 转述**：Cron harness 独立捕获 `gate-runner.py` 的 stdout/stderr 落盘存档（§3），quality-reviewer 读盘上文件，不读 agent 转述的内容——"要求 agent 贴出来+人工抽查"在无人值守场景等于没有缓解，已废弃这个写法（spotcat-e4 2026-08-26 复核指出） |
| 跨框架 adapter 一次性成本被低估 | 先在一个真实项目验证 adapter 稳定后再推广，不是全部项目并行起步 |
| gate 脚本自身有隐藏 bug，比 agent 自述更隐蔽 | 脚本必须有单元测试（合成/历史真实输出）；解析失败与业务 FAIL 分离成不同状态 |
| vendor 同步的 `.spotcat/vendor/` 与项目其余代码混淆 | `.gitattributes` 标记为 generated；`.spotcat-version` 文件明确来源版本 |
| LOC 阈值/config 字段设计过度超前于实际用量 | 先做当前已验证有用的字段，不为假设中的未来项目类型预建 |
