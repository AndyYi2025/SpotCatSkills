# Quant Project Context Template

Each quant project should fill in these fields in its CLAUDE.md or sprint plan.

## Data Paths

- Market data root: (e.g. `D:/quantdata/markets/CNFUT/`)
- Historical data format: (e.g. parquet, csv)
- Date range available: (e.g. 2018-01-01 to present)

## Market Rules

- Market: (CN Future / CN Stock / US Stock / US Option)
- Trading session: (e.g. 09:00-15:00 CST)
- Settlement rules: (e.g. T+1 for CN stocks)
- Commission rate: (e.g. 0.0001 per contract)

## Trading Constraints

- Max position size: (e.g. 10 contracts)
- Max daily loss: (e.g. 5% of capital)
- Allowed order types: (e.g. limit only, no market orders)

## Risk Parameters

- Max drawdown threshold: (e.g. 15%)
- Min Sharpe ratio: (e.g. 1.0)
- Min trade count for backtest: (e.g. 30)

## Test Configuration

- Test framework: (e.g. pytest, unittest)
- Backtest framework: (e.g. nautilus_trader, vnpy, custom)
- Test command: (e.g. `pytest tests/ -v`)
- Backtest command: (e.g. `python -m backtest.run --strategy {strategy}`)
