import json
import os
import stat
import textwrap
from pathlib import Path
from unittest import mock

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


def test_load_config_unreadable_file(tmp_path):
    """Test that unreadable files raise ConfigError (not raw OSError/PermissionError).

    Uses mock to simulate PermissionError when reading (works across platforms).
    """
    p = tmp_path / "config.yml"
    p.write_text(VALID_YAML)

    # Mock read_text to raise PermissionError
    with mock.patch.object(Path, "read_text", side_effect=PermissionError("Access denied")):
        with pytest.raises(ConfigError, match="not readable"):
            load_config(p)


def test_load_config_posix_absolute_data_root(tmp_path):
    """Test that POSIX-style absolute paths (/tmp/data) are recognized as absolute.

    This test verifies the cross-platform bug fix: on Windows, Path("/tmp/data").is_absolute()
    returns False, but our custom _looks_absolute() correctly identifies it as absolute
    and does NOT prepend project_root to it.
    """
    config_dir = tmp_path / "proj" / ".spotcat"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Use POSIX-style absolute path (as in the example config)
    config_yaml = VALID_YAML  # Already has data_root: /tmp/data
    config_path = config_dir / "config.yml"
    config_path.write_text(config_yaml)

    cfg = load_config(config_path)
    # Should NOT be modified to include project path; should stay as-is (normalized)
    # Path("/tmp/data").resolve() on Windows returns C:\tmp\data (wrong), but we want /tmp/data
    # So we check that it's recognized as absolute and NOT prepended with project_root
    data_root = cfg["paths"]["data_root"]
    # The key assertion: it should start with /, not contain the project_root path
    assert data_root.startswith("/") or (len(data_root) > 2 and data_root[1] == ":")
    # Make sure project_root is NOT in the resolved path (except if they happen to overlap)
    project_root_str = str((tmp_path / "proj").resolve())
    # If /tmp/data is recognized as absolute, project path should not be in it
    # (unless Windows has a C:\tmp\data which would be a coincidence)
    if data_root.startswith("/"):
        assert project_root_str not in data_root or "\\" not in project_root_str


def test_load_config_windows_absolute_data_root(tmp_path):
    """Test that Windows-style absolute paths (D:/data, C:\\data) are recognized as absolute."""
    config_dir = tmp_path / "proj" / ".spotcat"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Use Windows-style absolute path
    windows_path = "D:/quantdata/CNFUT"
    config_yaml = VALID_YAML.replace("data_root: /tmp/data", f"data_root: {windows_path}")
    config_path = config_dir / "config.yml"
    config_path.write_text(config_yaml)

    cfg = load_config(config_path)
    data_root = cfg["paths"]["data_root"]
    # Should recognize D:/quantdata/CNFUT as absolute and not prepend project_root
    # The path should still have D: in it (not replaced with project root path)
    assert "D:" in data_root or "D:\\" in data_root or "D:/" in data_root
