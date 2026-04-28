# SpotCatSkills

OpenClaw agent skills for automated development via ACP (Agent Communication Protocol).

## Skills

### spotcat-sprint-dev

General Spec-Driven Development (SDD). Automates: spec → implement → review → done.

Use for: any software feature development (web, tools, infra, etc.)

### spotcat-quant-dev

Quant-adapted SDD with 3-layer test gates. Same state machine as sprint-dev, but with:
- Quant-specific scoring (strategy logic, data integrity, risk safety)
- 3-layer testing: unit tests → backtest → data validation
- 7 root cause types (5 original + data quality + overfitting)

Use for: quantitative trading feature development

### spotcat-quant-research

Quant research loop. Automates: hypothesis → explore → prototype → backtest → evaluate → report.

Use for: exploratory strategy research and validation

## Quick Start

1. Install as an OpenClaw plugin
2. Choose a skill based on your task type
3. Create a sprint/research plan from the template
4. Let the Cron-driven state machine execute

## Safety

- Paper → real trading always requires human approval
- No synthetic data in backtests
- No auto-trading without explicit enable
- See `shared/safety-rules.md` for full list

## Architecture

See `docs/architecture.md` for skill relationships and state machine details.

## License

MIT
