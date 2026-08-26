import json
import textwrap
from pathlib import Path

import pytest

from spotcat_gates.config import ConfigError, load_config

VALID_YAML = textwrap.dedent("""\
    version: 1
    spotcat_schema_version: 1
    paths:
      data_root: /tmp/data
      data_format: parquet
      expected_date_range: { start: "2024-01-01", end: "2024-12-31" }
    commands:
      test: "pytest tests/ -v --json-report --json-report-file=.spotcat/last-test-result.json"
      backtest: "python -m backtest.run --strategy {strategy}"
    thresholds:
      min_sharpe: 1.0
      max_drawdown: 0.15
      min_trades: 30
      max_oos_is_gap_pct: 50
    code_budget:
      max_file_loc: 500
      ignore_file: .codebudgetignore
    safety:
      paper_only: true
      live_enable_flag_path: .spotcat/LIVE_ENABLED
      global_kill_switch: "~/.spotcat/GLOBAL_LIVE_ENABLE"
      idempotency_key_format: "{strategy_id}_{signal_timestamp}_{side}"
    """)


def test_load_config_valid(tmp_path):
    p = tmp_path / "config.yml"
    p.write_text(VALID_YAML)
    cfg = load_config(p)
    assert cfg["safety"]["paper_only"] is True
    assert cfg["thresholds"]["min_sharpe"] == 1.0


def test_load_config_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yml")


def test_load_config_missing_required_field(tmp_path):
    bad = VALID_YAML.replace("  min_sharpe: 1.0\n", "")
    p = tmp_path / "config.yml"
    p.write_text(bad)
    with pytest.raises(ConfigError, match="schema"):
        load_config(p)


def test_load_config_wrong_schema_version(tmp_path):
    bad = VALID_YAML.replace("spotcat_schema_version: 1", "spotcat_schema_version: 2")
    p = tmp_path / "config.yml"
    p.write_text(bad)
    with pytest.raises(ConfigError, match="spotcat_schema_version"):
        load_config(p)


def test_load_config_relative_data_root(tmp_path):
    """Test that relative data_root is resolved against the project root.

    Config at: <tmp>/some/nested/.spotcat/config.yml
    data_root: ../data (relative)
    Expected result: <tmp>/some/data/ (resolved to project root's parent/data)
    """
    # Create directory structure: <tmp>/some/nested/.spotcat/ and <tmp>/some/data/
    project_root = tmp_path / "some"
    config_dir = project_root / "nested" / ".spotcat"
    data_dir = project_root / "data"

    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create config with relative data_root
    config_yaml = VALID_YAML.replace("data_root: /tmp/data", "data_root: ../data")
    config_path = config_dir / "config.yml"
    config_path.write_text(config_yaml)

    # Load and verify data_root is resolved correctly
    cfg = load_config(config_path)
    expected_data_root = str(data_dir.resolve())
    assert cfg["paths"]["data_root"] == expected_data_root
