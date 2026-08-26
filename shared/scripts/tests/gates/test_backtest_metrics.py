import json
from pathlib import Path

from spotcat_gates.data_files import hash_data_files, resolve_data_files
from spotcat_gates.gates.backtest_metrics import check_backtest_metrics


def _config(project_root, data_root):
    return {
        "paths": {
            "data_root": str(data_root),
            "data_format": "csv",
            "expected_date_range": {"start": "2024-01-01", "end": "2024-01-01"},
        },
        "commands": {"test": "true", "backtest": "python -c \"pass\""},
        "thresholds": {
            "min_sharpe": 1.0, "max_drawdown": 0.2, "min_trades": 10, "max_oos_is_gap_pct": 50,
        },
    }


def _write_result(project_root, data_hash, **overrides):
    result = {
        "sharpe_ratio": 1.5, "max_drawdown": 0.1, "win_rate": 0.55, "trade_count": 40,
        "profit_factor": 1.3, "in_sample_sharpe": 1.6, "out_sample_sharpe": 1.4,
        "lookahead_check": "not_run", "data_hash": data_hash, "generated_at": "2026-08-26T00:00:00Z",
    }
    result.update(overrides)
    out = project_root / ".spotcat" / "last-backtest-result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result), encoding="utf-8")


def test_pass_when_thresholds_met_and_hash_matches(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    real_hash = hash_data_files(resolve_data_files(config), Path(config["paths"]["data_root"]))
    _write_result(project_root, data_hash=real_hash)

    r = check_backtest_metrics(config, project_root)
    assert r.status == "PASS"
    assert r.evidence_tier == "A"


def test_fail_when_sharpe_below_threshold(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    real_hash = hash_data_files(resolve_data_files(config), Path(config["paths"]["data_root"]))
    _write_result(project_root, data_hash=real_hash, sharpe_ratio=0.2)

    r = check_backtest_metrics(config, project_root)
    assert r.status == "FAIL"
    assert "sharpe" in r.details["reason"].lower()


def test_fail_when_data_hash_mismatch(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    _write_result(project_root, data_hash="stale-hash-from-before-data-changed")

    r = check_backtest_metrics(config, project_root)
    assert r.status == "FAIL"
    assert "data_hash" in r.details["reason"]


def test_error_when_output_file_missing(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()
    config = _config(project_root, data_root)

    r = check_backtest_metrics(config, project_root)
    assert r.status == "ERROR"
    assert "not found" in r.details["reason"]


def test_error_when_output_fails_schema(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()
    out = project_root / ".spotcat" / "last-backtest-result.json"
    out.parent.mkdir(parents=True)
    out.write_text(json.dumps({"sharpe_ratio": "not-a-number"}), encoding="utf-8")

    config = _config(project_root, data_root)
    r = check_backtest_metrics(config, project_root)
    assert r.status == "ERROR"
    assert "schema" in r.details["reason"]


def test_fail_when_oos_is_gap_too_large(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    real_hash = hash_data_files(resolve_data_files(config), Path(config["paths"]["data_root"]))
    # (2.0 - 0.5) / 2.0 = 75% gap, over the 50% threshold
    _write_result(project_root, data_hash=real_hash, in_sample_sharpe=2.0, out_sample_sharpe=0.5)

    r = check_backtest_metrics(config, project_root)
    assert r.status == "FAIL"
    assert "oos" in r.details["reason"].lower() or "gap" in r.details["reason"].lower()


def test_error_when_expected_date_range_malformed(tmp_path):
    """Amendment 2: a malformed expected_date_range.start should raise DataFilesError
    inside the data-hash verification step, which check_backtest_metrics must catch
    and surface as ERROR (not an uncaught exception) -- even though the backtest
    output file exists and is otherwise schema-valid."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    config["paths"]["expected_date_range"]["start"] = "not-a-date"
    _write_result(project_root, data_hash="irrelevant-because-date-range-is-malformed")

    r = check_backtest_metrics(config, project_root)
    assert r.status == "ERROR"
    assert "reason" in r.details


def test_fail_when_in_sample_sharpe_is_zero(tmp_path):
    """in_sample_sharpe == 0 must not silently skip the oos/is gap check (which would
    let a catastrophic out_sample_sharpe slip through as PASS since out_sample_sharpe
    is otherwise never checked on its own) -- fail closed instead."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    real_hash = hash_data_files(resolve_data_files(config), Path(config["paths"]["data_root"]))
    _write_result(project_root, data_hash=real_hash, in_sample_sharpe=0.0, out_sample_sharpe=-8.0)

    r = check_backtest_metrics(config, project_root)
    assert r.status == "FAIL"
    assert "cannot compute" in r.details["reason"].lower()


def test_error_when_backtest_command_exits_nonzero(tmp_path):
    """A nonzero exit code means the backtest run itself failed -- must not fall through
    to reading a stale result file left over from a previous successful run."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    config["commands"]["backtest"] = 'python -c "import sys; sys.exit(1)"'
    real_hash = hash_data_files(resolve_data_files(config), Path(config["paths"]["data_root"]))
    _write_result(project_root, data_hash=real_hash)  # stale but well-formed and threshold-passing

    r = check_backtest_metrics(config, project_root)
    assert r.status == "ERROR"
    assert "exit" in r.details["reason"].lower()
