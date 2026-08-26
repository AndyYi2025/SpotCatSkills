import json
import pathlib

# Reuse the real gate-side config loader and hashing functions instead of reimplementing the
# hash algorithm by hand. This depends on `spotcat_gates` being importable, which the test that
# drives this fixture guarantees by setting PYTHONPATH to shared/scripts before invoking
# gate_runner (that env var propagates to this subprocess since none of the gate/subprocess
# calls in between override `env`). Calling load_config() here -- the exact same function
# gate_runner uses -- rather than hand-building a config dict also means this can never drift
# from how the real gate resolves data_root / builds the file list, not just from how it hashes.
from spotcat_gates.config import load_config
from spotcat_gates.data_files import hash_data_files, resolve_data_files

config = load_config(".spotcat/config.yml")
files = resolve_data_files(config)
data_hash = hash_data_files(files, pathlib.Path(config["paths"]["data_root"]))

result = {
    "sharpe_ratio": 1.8, "max_drawdown": 0.08, "win_rate": 0.6, "trade_count": 12,
    "profit_factor": 1.5, "in_sample_sharpe": 1.9, "out_sample_sharpe": 1.7,
    "lookahead_check": "not_run", "data_hash": data_hash, "generated_at": "2026-08-26T00:00:00Z",
}
out = pathlib.Path(".spotcat/last-backtest-result.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result))
