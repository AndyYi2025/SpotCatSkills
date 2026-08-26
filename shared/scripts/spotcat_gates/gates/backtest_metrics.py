from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema

from spotcat_gates.data_files import DataFilesError, hash_data_files, resolve_data_files
from spotcat_gates.result import GateResult

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "backtest-result.schema.json"
_OUTPUT_RELPATH = ".spotcat/last-backtest-result.json"


def check_backtest_metrics(config: dict, project_root: Path) -> GateResult:
    project_root = Path(project_root)
    cmd = config["commands"]["backtest"]
    try:
        subprocess.run(cmd, shell=True, cwd=project_root, timeout=3600)
    except (subprocess.SubprocessError, OSError) as e:
        return GateResult(
            gate="backtest-metrics", status="ERROR", evidence_tier="A",
            details={"reason": f"backtest command failed to run: {e}"},
        )

    out_path = project_root / _OUTPUT_RELPATH
    if not out_path.is_file():
        return GateResult(
            gate="backtest-metrics", status="ERROR", evidence_tier="A",
            details={"reason": f"result file not found: {out_path}"},
        )

    try:
        result = json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return GateResult(
            gate="backtest-metrics", status="ERROR", evidence_tier="A",
            details={"reason": f"result file is not valid JSON: {e}"},
        )

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=result, schema=schema)
    except jsonschema.ValidationError as e:
        return GateResult(
            gate="backtest-metrics", status="ERROR", evidence_tier="A",
            details={"reason": f"result failed schema validation: {e.message}"},
        )

    try:
        expected_hash = hash_data_files(resolve_data_files(config), Path(config["paths"]["data_root"]))
    except DataFilesError as e:
        return GateResult(
            gate="backtest-metrics", status="ERROR", evidence_tier="A",
            details={"reason": str(e)},
        )
    if result["data_hash"] != expected_hash:
        return GateResult(
            gate="backtest-metrics", status="FAIL", evidence_tier="A",
            details={
                "reason": "data_hash mismatch: data files changed since backtest ran (or wrong data was used)",
                "expected": expected_hash, "got": result["data_hash"],
            },
        )

    th = config["thresholds"]
    if result["sharpe_ratio"] < th["min_sharpe"]:
        return GateResult(
            gate="backtest-metrics", status="FAIL", evidence_tier="A",
            details={"reason": f"sharpe_ratio {result['sharpe_ratio']} < min_sharpe {th['min_sharpe']}"},
        )
    if result["max_drawdown"] > th["max_drawdown"]:
        return GateResult(
            gate="backtest-metrics", status="FAIL", evidence_tier="A",
            details={"reason": f"max_drawdown {result['max_drawdown']} > threshold {th['max_drawdown']}"},
        )
    if result["trade_count"] < th["min_trades"]:
        return GateResult(
            gate="backtest-metrics", status="FAIL", evidence_tier="A",
            details={"reason": f"trade_count {result['trade_count']} < min_trades {th['min_trades']}"},
        )

    is_s, oos_s = result["in_sample_sharpe"], result["out_sample_sharpe"]
    if is_s != 0:
        gap_pct = abs(is_s - oos_s) / abs(is_s) * 100
        if gap_pct > th["max_oos_is_gap_pct"]:
            return GateResult(
                gate="backtest-metrics", status="FAIL", evidence_tier="A",
                details={"reason": f"oos/is gap {gap_pct:.1f}% > threshold {th['max_oos_is_gap_pct']}%"},
            )

    return GateResult(
        gate="backtest-metrics", status="PASS", evidence_tier="A",
        details={k: result[k] for k in (
            "sharpe_ratio", "max_drawdown", "trade_count", "in_sample_sharpe", "out_sample_sharpe"
        )},
    )
