# Safety Rules

Hard rules enforced across all quant skills. Violations result in score veto (total = 0).

1. **No synthetic/fake data** — All backtests must use real market data from documented paths
2. **Paper → real requires human approval** — The agent must never auto-promote from paper to live trading
3. **No auto-trading without explicit human enable** — Trading must be opt-in, not opt-out
4. **Backtest must use real data** — Data paths must be verified against project CLAUDE.md
5. **Credentials via env vars only** — No API keys, passwords, or tokens hardcoded in source code
6. **Position limits enforced in code** — Not just in config, but validated in the strategy logic
7. **First run must be paper mode** — Any new strategy's first execution must be paper trading
