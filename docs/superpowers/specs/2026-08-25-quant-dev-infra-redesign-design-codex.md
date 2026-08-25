# SpotCat Quant-Dev Infra Redesign — Independent Design (codex)

**作者：** Claude session working in `D:\codebase\personal\SpotCat`
**日期：** 2026-08-25
**约束：** 本文档独立写成，未参照 `2026-08-25-quant-dev-infra-redesign-design.md`（同目录另一份方案），仅基于本会话对 SpotCat 实际文件的阅读和与 botapp-c0 几轮讨论中已经对齐的事实性判断（脚本三分类、position-limit 行为性测试、位移重放测试、跨框架 backtest-result schema、config 层需求、内容先行/版本纪律后行）。组织方式、优先级排序、风险取舍按本会话自己的判断给出，允许与另一份方案分歧。

---

## 0. 出发点：这次重新设计到底为了解决什么

用户的真实场景是：**一个人，多个量化项目，用 SpotCat 的 skill 定义驱动 Cron-based agent 自动开发**。当前 SpotCat 100% 是 markdown prompt，没有一行可执行代码——所有"检查"最终都退化成"agent 说它检查过了"。这在无人值守、7×24 跑 Cron 的场景下是致命的：没有人会实时盯着每一轮 quality-review 的结论是不是编的。

这决定了本文档的组织原则，和另一份方案可能不同：**我不按"SDD 的哪个 phase"或"哪些好脚本化"来分组，而是按"这一层出错的代价有多大（blast radius）"来排优先级**。原因：脚本化容易的东西不一定是最该优先脚本化的东西——比如"函数是否有类型提示"极易脚本化但出错代价趋近于零；"仓位限制有没有真的生效"较难脚本化但出错代价是真实亏钱。无人值守场景下，应该优先把代价最高的环节钉死，而不是优先做最容易做的。

## 1. 优先级分层（本文档的主线）

| 层级 | 内容 | 出错代价 | 本文档章节 |
|---|---|---|---|
| P0 | 资金安全硬门（kill switch、仓位限制、凭证、防重复下单） | 真实亏钱/失控交易 | §2 |
| P1 | 回测证据完整性（脚本解析真实数字，而非 agent 自述） | 整套 SDD 门控建立在假数据上，所有下游判断失真 | §3 |
| P2 | 可复现性/数据完整性（data hash、前瞻偏差重放测试） | P1 的数字本身会漂移或被静默污染 | §4 |
| P3 | 多项目分发与配置层 | 效率/维护成本，不影响正确性 | §5 |
| P4 | 代码/流程卫生（LOC 预算、PARTIAL 记录、prompt 顺序） | 返工成本，不影响正确性或安全 | §6 |

**落地顺序 = P0 → P1 → P2 → P3 → P4**，不是按"哪个先讨论到"或"哪个改动小"排序。P3（版本化/多项目分发）虽然是这次升级的直接触发原因（"我这么多项目"），但它排在 P0-P2 之后——**先保证单个项目的门控是真的，再谈把这套门控复制到 N 个项目**；顺序反过来的话，是在把一个可能有假绿漏洞的机制原样复制 N 份。

---

## 2. P0：资金安全硬门

这一层的判断标准不是"能不能脚本化"（其实都能），而是"允不允许有任何 advisory 残留"。P0 里任何一条都不能是"建议 agent 检查"，必须是脚本 exit code 决定，agent 无法覆盖。

### 2.1 现状盘点

- `shared/safety-rules.md` 7 条规则全部是 prose，目前的强制手段是"quality-review 阶段 agent 检查，违反则总分=0 veto"——**veto 本身是真的（分数计算写在 quant-quality-reviewer-prompt.md 里），但"有没有违反"这个判断目前 100% 靠 agent 读代码得出**，这是唯一的信任支点，也是最薄弱的一环。
- `quant-quality-reviewer-prompt.md` 现在的执行顺序是 1.读文件 → 2.验证3层门控 → 3.打分 → 4.安全检查（veto）→ 5.算总分——安全检查排在倒数第二步。对比 `spotcat-sprint-dev/references/quality-reviewer-prompt.md`，那边安全检查是 step 2，"最先执行、一票否决"。**quant 版本的检查顺序目前比通用版本更弱**，这本身就是个信号：量化场景理应比一般业务代码更严格，现状却相反。

### 2.2 设计

**2.2.1 仓位限制：从"存在性"改成"行为性"契约**

不接受"静态扫描代码里有没有限仓相关字符串"这种检查——`import position_limit_check` 但从不调用，静态扫描一样会通过。改为契约：strategy 代码必须提供一条命名规范化的测试（如 `test_position_limit_enforced`），其中必须有形如 `assert placed_qty <= max_position` 的具体数值断言，脚本只检查「这条测试存在 + 通过」，不猜代码语义。这条测试不存在或不通过 = P0 硬失败，无条件退回 implementing，不计入正常的 fail_streak 宽容轮次。

**2.2.2 双层 kill switch，不是单层 flag**

之前讨论过 `.spotcat/config.yml` 里放一个 `live_enable_flag_path`（项目级）。这里补一层：**再加一个项目仓库之外的全局开关**（例如 `~/.spotcat/GLOBAL_LIVE_ENABLE`，或者一个环境变量），live 交易必须"全局开关 AND 项目开关"同时为真才放行。

理由：这是"solo dev 管理 N 个项目"这个场景特有的风险——单项目 flag 模型下，用户只要有一个项目的 flag 忘记复位就可能出问题；全局开关相当于一个总闸，出事时只需要拉一个开关就能让所有项目同时停止 live 交易，不需要逐项目确认。这条在通用软件工程治理体系里不会自然出现（没有"资金"这个概念），是量化场景特有的，值得单独列出。

**2.2.3 防重复下单（idempempotency）——目前完全没人提过，这是个真实缺口**

Cron 驱动、1小时一轮、implementing 阶段是异步 spawn（最长1.5h）。如果某一轮执行中途崩溃/超时/被杀，下一轮重试时，有没有机制保证不会对同一个信号重复下单？现在的 7 条 safety-rules 里没有这条。建议新增规则：

- 每个信号/订单必须带幂等 key（比如 `{strategy_id}_{signal_timestamp}_{side}`），下单前脚本查询是否已有相同 key 的订单记录，有则跳过。
- 这条不是"建议 agent 小心"，必须是下单执行路径里的强制代码逻辑，而且要有对应的行为性测试（类似 2.2.1 的模式：`test_duplicate_signal_not_double_ordered`）。

**2.2.4 凭证扫描**

`safety-rules.md` L9 已经写了规则，但落地是 agent 读代码判断。改为脚本：secret scanner（gitleaks 或等价正则/熵检测）跑在 diff 上，P0 级别 veto，不打折扣。

### 2.3 P0 层的一个通用原则：fail-closed，不做默认值

任何 P0 相关的配置字段（仓位上限、live_enable 开关路径、幂等 key 格式）在 `.spotcat/config.yml` 里缺失时，脚本必须**拒绝运行并报错**，不能静默用某个"安全默认值"顶上。安全默认值这个概念本身就是隐患——"没配置就当作最保守"这个逻辑本身也是一段可能写错的代码，缺失配置更应该被当成"这个项目还没接入 P0 门控"的显式失败，逼着用户去补，而不是允许它悄悄跑起来。

---

## 3. P1：回测证据完整性

这一层解决的是 QUALITY-GATES-006 那个问题的量化版本：**"agent 报告 Sharpe=1.34" 这句话本身不是证据，除非能证明这个数字来自脚本对真实回测输出的解析，而不是 agent 读了一眼输出文件之后口算/编造的**。

### 3.1 设计要点（与之前几轮讨论一致，这里不重复展开机制本身，只强调排序判断）

- 每个项目的 `backtest_command` 必须产出符合 SpotCat 定义的规范 schema 的 JSON（`shared/schemas/backtest-result.schema.json`：sharpe_ratio / max_drawdown / win_rate / trade_count / profit_factor / in_sample_sharpe / out_sample_sharpe / lookahead_check / data_hash / generated_at）。
- 不同回测框架（nautilus_trader/vnpy/custom）原生输出各不相同，靠**每个项目自己写一次性 adapter** 转换成规范 JSON，SpotCat 侧的 gate 脚本永远只认这一份 schema，不需要认识任何具体框架。
- 统一 stdout 协议：`{"gate": "...", "pass": bool, "evidence_tier": "A|B|C", "details": {...}}`，quality-reviewer 的 prompt 改成"跑 gate-runner，读 JSON 填表"，而不是自己判断。

### 3.2 为什么这一层排在 P0 之后、P2/P3 之前

因为 P1 是**其余所有量化质量判断的地基**——3 层测试门控、过拟合检测、spec-review 的"正确性"打分，全都间接依赖"这个 Sharpe/回撤数字是真的"这个前提。如果这一层还是 agent 自述，那么无论 P2（数据完整性）和 P3（多项目分发）做得多精致，复制的都是一个可能被伪造的地基。**P1 不落地之前，讨论"要不要给 N 个项目做统一版本管理"是没有意义的——你会把假绿machinery 版本化分发到 N 个项目。**

### 3.3 一个容易被忽略的推论：谁测试这些脚本

把检查从 prompt 移到脚本，并没有消灭"谁来验证验证者"这个问题，只是把它从"agent 有没有诚实检查"搬到了"脚本本身写得对不对"。区别在于：脚本的错误更隐蔽——没有人会像质疑 agent 结论那样怀疑一段已经跑通很多次的解析代码，一旦 `parse_backtest_output()` 有个边界 bug（比如某个框架版本升级后字段名变了，脚本悄悄解析出 0 却被判定为"低于阈值，正常 FAIL"而不是"解析失败"），会在所有项目的所有轮次里静默产生错误判断，比单次 agent 自述错误的影响面大得多。

建议：gate 脚本本身要有单元测试（喂已知的合成/历史真实输出，断言解析出的数字符合预期），并且**解析失败和"指标真实低于阈值"必须是两种不同的退出码/状态**（不能把 parse error 归并成"gate FAIL"，那样等于把工具bug 伪装成了业务失败，反而更难发现）。这条建议不在另一份方案讨论范围内提到过，属于我认为容易被漏掉、必须补的一点。

---

## 4. P2：可复现性与数据完整性

### 4.1 前瞻偏差：位移重放测试

之前讨论过的方案：信号函数分别喂 `data[:T]` 和 `data[:T+k]`，断言 T 处输出逐位相同。这条脚本能抓住"代码里直接用了未来数据"的大多数真实 bug。抓不住的是"数据在 T 时刻本身是否真的已披露"这类时点可得性问题（比如用当天收盘价在收盘前决策，重放测试本身是确定性的，看不出问题），这部分仍需要 LLM 读代码。**这条我判定为 P2 而不是 P1**，因为它保护的是"数字长期可信"，而不是"这一次的数字是不是编的"——P1 先解决有没有造假，P2 再解决会不会漂移/被污染。

### 4.2 历史数据不可变性：data_hash

`backtest-result.schema.json` 里带一个 `data_hash` 字段，脚本对本次用到的数据文件区间算 hash 写进结果。这不是为了当次门控用的，是为了**未来审计**：某天回测结果对不上，第一件要排除的事就是"数据源是不是被静默改过"（数据商重新调整了某天的价格、修复了一个bug、静默补了缺失数据）——没有 hash 记录，这个问题永远无法确认，只能靠猜。

### 4.3 日期缺口/schema 校验

沿用之前讨论：脚本读 `.spotcat/config.yml` 里的 `data_root`，实际列出文件覆盖的日期区间，跟声明的区间做差集，无缺口才 PASS。这条纯粹是文件系统操作，没有语义判断空间，P2 里最简单的一条，但因为是其它 P2/P1 判断的输入前提（数据不完整会导致 Sharpe 算出来就是错的），仍然要在 P1/P2 之间及早跑。

---

## 5. P3：多项目分发与配置层

### 5.1 契约范围：整个仓库，不是 `shared/`

`plugin.json` 是给整个仓库定版本号的（`skills` 数组指向 `./skills`），consuming project 是整体 pin 一个版本，不是分别 pin `shared/` 和某个 skill 的子目录。所以"改动是否需要走版本纪律"的判定范围应该是**整个仓库，除了 `quant-context.md` 这类模板文件被各项目实例化后的具体字段值**（那些值活在各项目自己的 `CLAUDE.md`/`.spotcat/config.yml` 里，从不回写这个仓库）。这一点如果不明确，后续改 `skills/spotcat-quant-dev/references/*.md` 或新增 `shared/scripts/*` 时会有人误以为"不在 shared/ 里就不算 breaking change"，从而绕开该走的版本纪律。

### 5.2 反对用 git submodule 钉版本

这是我判断和大概率与另一份方案会分歧的一点，单独讲清楚理由。

Submodule 在**人工操作**为主的仓库里是合理选择，但 SpotCat 的实际运行模型是**Cron 驱动的自主 agent 在做 git 操作**（implementing 阶段 agent 会自己 commit）。这个模型下 submodule 有几个具体风险：

1. Agent 在 consuming project 里做 `git add -A && git commit` 这类操作时，如果不清楚 submodule 的存在，很容易只提交了 submodule 指针的"脏状态"（detached HEAD 上有本地改动但没提交/没推），下一次 `git submodule update` 直接把这些改动丢掉，而且不会有明显报错——这是那种要过几周才会被发现的静默数据丢失。
2. Submodule 更新（`git submodule update --remote`）本身需要一次显式的人工/agent 决策，如果这个决策也交给自动化 Cron 流程做，等于是把"要不要升级 SpotCat 版本"这件事也自动化了，而这恰恰是本次重新设计想避免自动发生的事（升级应该经过 CHANGELOG 阅读 + canary 验证，不该被 Cron 悄悄拉新版本）。

**替代方案**：consuming project 根目录放一个 `.spotcat-version`（内容就是 SpotCat 仓库的一个 commit SHA 或 tag），加一个 `spotcat sync` 脚本（浅 clone/checkout 到 `.spotcat/vendor/` 目录，或者直接用 `git archive` 导出对应版本的文件树覆盖过去）。这个模型下：

- 升级永远是显式动作（跑一次 `spotcat sync --to v1.2.0`），不会被 Cron 自动触发。
- `.spotcat/vendor/` 目录不是一个嵌套 git 仓库，agent 在 consuming project 里做正常的 `git commit` 不会碰到 submodule 那类"指针脏了但没人发现"的问题——vendor 目录的内容变化会像普通文件改动一样被正常 commit 记录下来，出问题也是可见、可 diff、可 revert 的。
- 代价是没有 submodule 自带的"这是外部依赖"的语义标记，但这个可以靠 `.spotcat-version` 文件 + `.gitattributes` 标记 vendor 目录为 generated 内容来弥补，成本远低于 submodule 在自主 agent 操作下的风险。

### 5.3 `.spotcat/config.yml`

沿用之前讨论的设计（data paths / commands / thresholds / code_budget / safety），补两条原则：

- **schema 校验先于任何 gate 运行**：gate-runner 启动时先校验 config 是否符合 JSON schema，字段缺失/类型错误直接拒绝执行（呼应 §2.3 的 fail-closed 原则），不允许"缺字段就当默认值"这种静默降级，尤其是 P0/P1 相关字段。
- **config 本身也要版本化**：`.spotcat/config.yml` 加一个 `spotcat_schema_version` 字段，gate-runner 拒绝运行版本不匹配的 config（提示需要跑迁移脚本），避免"SpotCat 仓库升级了 schema，但某个项目的 config 还是老格式，脚本却安静地用旧字段名读出 undefined"这种漂移。

### 5.4 落地顺序：先在一个项目验证，再谈"分发"

"多项目复用"是驱动这次重新设计的直接诉求，但工程上应该反过来做：先在**一个**真实项目里把 P0-P2 的脚本层跑通、跑过至少一个真实 sprint 的 canary，再谈"怎么让另外 N 个项目复用同一套东西"的分发机制（submodule/vendor/CHANGELOG 纪律）。理由和 §1 的整体排序一致：分发机制解决的是"怎么复制"，如果被复制的东西本身没验证过，分发机制做得再好也只是把问题复制了 N 份。

---

## 6. P4：代码/流程卫生

这一层里的改动全部是"改进现有 markdown 内容"，出错代价最低，优先级也最低，但因为改动量小、容易顺手做，列在这里供实施时参考。

### 6.1 LOC 预算：不要在 quant-dev 里单开一个新数字

`skills/spotcat-sprint-dev/references/quality-reviewer-prompt.md` 里已经有一条**软性**的"文件 < 800 行"检查项（属于"代码质量"维度的扣分项，不是硬否决）。新增的 LOC 预算棘轮机制如果直接塞进 `quant-gates.md`，会出现三套并存的标准（sprint-dev 的 800 行软性 / quant-dev 新的硬顶数字 / `scoring.md` 里"可维护性"维度又一次模糊提到"单体文件过长"）。

建议：新建 `shared/code-budget.md`，两个 SDD skill 都引用它，统一一个数字（是收紧到更小还是维持接近 800，需要用户拍板，不要凭空造第三个数字），并且从"代码质量"维度里删掉旧的软性检查项，改成脚本硬否决——沿用之前讨论的棘轮/baseline/`.codebudgetignore`机制。**这条只该卡 SDD 的 quality-review 阶段，不该卡 quant-research 的 prototyping/backtesting 阶段**——研究原型允许先写乱，进 sprint 才收紧。

### 6.2 安全检查顺序前移

`quant-quality-reviewer-prompt.md` 当前顺序（读文件→3层门控→打分→安全检查→算总分）应该改成"读文件→安全规则/P0门控→3层门控→打分→算总分"，和 sprint-dev 已经在用的顺序对齐。这个改动本身很小（挪几行），但意义是把"最贵的错误"挪到最先检查，避免 agent 在注定要被 veto 的改动上浪费打分力气，也降低"先打完分才发现要否决"这种顺序本身带来的心理锚定（先看到一个不错的分数表，再看到veto，比一上来就veto，更容易让人/agent 产生"这个改动其实还行"的错觉）。

### 6.3 PARTIAL/NOT_DONE 强制记录

`skills/spotcat-quant-dev/assets/quant-sprint-plan-template.md` 目前的"评分记录"和"交付记录"表格没有强制字段要求"这一轮实际有没有做完"，一轮没过可以不留痕迹地重跑。建议加一个必填字段（比如"结果"列的取值从 `PASS/RETRY` 扩展为显式要求 `PASS/RETRY/PARTIAL/NOT_DONE` 四选一，且 `PARTIAL`/`NOT_DONE` 必须附一句话原因），倒不是复杂机制，是给 root-cause-analysis 阶段留下可读的历史，而不是靠猜。

---

## 7. 我认为最容易被漏掉、需要单独提醒用户的风险点

按重要性排序，不重复前面章节已经展开的内容：

1. **防重复下单幂等性**（§2.2.3）——目前 7 条 safety-rules 完全没覆盖，Cron+异步 spawn 的执行模型下这是个真实可能发生的故障模式，不是假设性风险。
2. **全局 kill switch**（§2.2.2）——单项目 flag 模型在"一人管多项目"场景下天然脆弱，一个总闸的边际成本很低。
3. **Gate 脚本自身的测试和"解析失败 vs 真实FAIL"的状态区分**（§3.3）——把检查从 prompt 移到脚本解决了"agent 会不会说谎"，但引入了"脚本会不会有 bug 且没人怀疑它"这个新问题，而且这个新问题比旧问题更隐蔽。
4. **不要用 git submodule**（§5.2）——这条我预期会和另一份方案冲突，需要讨论收敛；核心分歧点是"钉版本的机制要不要假设有人在人工审查每一次 git 操作"，而 SpotCat 的实际运行模型里大部分 git 操作是 Cron-driven agent 自主做的，人工审查是稀疏的、事后的。

---

## 8. 明确不做的事（现阶段）

- 正式 RFC 审批流程——solo 场景，没有需要说服的第二个人，写 CHANGELOG + rationale 已经够。
- Cell grid 单元格网格式的人机分工框架——SpotCat 现在 3 个 skill，量级完全用不上。
- 架构文档真源分级 + drift-scan cron——SpotCat 目前只有一份 `docs/architecture.md`，没有 RFC/ADR 体系，没有"多份文档互相冲突"的问题需要解决。
- 四档棘轮光谱的完整版——只需要 hard 和 ratchet 两档；量化 safety 规则必须永远 hard veto，不能因为"存量策略都没做仓位限制"就放行新策略，这条之前已经明确过，这里重申一次因为它和 P0 的设计原则直接相关。
- git submodule（本文档新增到排除列表，理由见 §5.2）。

## 9. 落地顺序总览

```
P0 (资金安全硬门)
  → 仓位限制行为性测试 + 双层kill switch + 幂等下单 + 凭证扫描
  → 在这一层验证前，不允许任何项目开放 live 交易
P1 (回测证据完整性)
  → backtest-result schema + 单项目 adapter + gate-runner 统一协议
  → 脚本自测（合成已知输出验证解析正确性）
P2 (可复现性/数据完整性)
  → 位移重放测试（前瞻偏差）+ data_hash + 日期缺口校验
—— 以上三层在同一个"试点项目"里跑通，且至少完成一次真实 sprint 的 canary 验证 ——
P3 (多项目分发)
  → .spotcat-version + spotcat sync 脚本（不用 submodule）
  → config schema 版本化 + fail-closed 校验
  → CHANGELOG 纪律从这里正式启动（P0-P2 阶段的改动不需要背这个负担，因为还没有第二个消费者）
P4 (代码/流程卫生)
  → LOC 预算统一 + 安全检查顺序前移 + PARTIAL/NOT_DONE 强制记录
  → 可以和 P3 并行做，互不阻塞
```

## 10. 留给用户拍板的问题

1. LOC 预算最终数字：维持接近现有 sprint-dev 的 800，还是收紧到 megaview 的 500？两个 skill 需要统一成一个数字。
2. 全局 kill switch 用什么形式最顺手：本机文件、环境变量，还是要考虑跨机器同步（如果同一个人用多台机器跑不同项目的 Cron）？
3. 是否接受用 `.spotcat-version` + sync 脚本替代 submodule？如果坚持要 submodule 的语义清晰度，需要额外设计"agent 在 consuming project 里做 git 操作时如何安全地跳过/保护 submodule 状态"的具体规则，而不是假设不会出问题。
