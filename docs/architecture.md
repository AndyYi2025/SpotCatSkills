# SpotCatSkills Architecture

## Overview

SpotCatSkills is an OpenClaw plugin containing three skills for automated development via ACP (Agent Communication Protocol):

1. **spotcat-sprint-dev** — General Spec-Driven Development (SDD)
2. **spotcat-quant-dev** — Quant-adapted SDD with 3-layer test gates
3. **spotcat-quant-research** — Quant research loop

## Skill Relationships

```
spotcat-sprint-dev (general SDD)
    └── spotcat-quant-dev (quant-adapted SDD, same state machine + quant overrides)
spotcat-quant-research (independent research state machine)
```

- `spotcat-sprint-dev` is standalone — works for any project type
- `spotcat-quant-dev` shares the same 6-phase SDD state machine but replaces prompts, scoring, and gates with quant-specific versions
- `spotcat-quant-research` is a separate 7-phase state machine for exploratory research
- Both quant skills share `shared/` context (safety rules, quant context, scoring principles)

## State Machines

### SDD (sprint-dev, quant-dev)
```
pending → implementing → spec-review → quality-review → root-cause → done/blocked
```

- Cron-driven, 1h interval
- implementing: async (ACP sessions_spawn, 1.5h max)
- spec-review, quality-review, root-cause: sync within Cron turn
- Hard gates: tests pass → correctness ≥2.5/3 → total ≥9/10

### Research (quant-research)
```
hypothesis → exploring → prototyping → backtesting → evaluating → reporting → done/blocked
```

- Cron-driven, 1h interval
- exploring, prototyping, backtesting: async (ACP sessions_spawn)
- hypothesis, evaluating, reporting: sync within Cron turn
- Gate: total ≥4.0/5.0 → GO

## 3-Layer Test Gates (quant-dev only)

1. **Unit Tests** — Logic correctness, edge cases
2. **Backtest** — Real data, performance metrics, no look-ahead bias
3. **Data Validation** — Correct paths, complete dates, no synthetic data

## Safety Boundary

The agent never auto-promotes from paper to live trading. This is a hard rule enforced in:
- `shared/safety-rules.md` (rule #2)
- `spotcat-quant-dev/SKILL.md` (deploy boundary section)
- `spotcat-quant-research/SKILL.md` (safety rules section)

## Adding New Skills

1. Create `skills/<skill-name>/` with SKILL.md, references/, assets/
2. Add skill path to `plugin.json` skills array
3. If quant-related, reference `shared/` for context and safety rules
4. Follow the naming convention: `spotcat-<domain>-<purpose>`
