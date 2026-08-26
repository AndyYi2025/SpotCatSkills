import json
import textwrap
from pathlib import Path

from spotcat_gates.gate_runner import _is_excluded, run_all_gates

CONFIG_YAML = textwrap.dedent("""\
    version: 1
    spotcat_schema_version: 1
    paths:
      data_root: {data_root}
      data_format: csv
      expected_date_range: {{ start: "2024-01-01", end: "2024-01-01" }}
    commands:
      test: "python {test_script}"
      backtest: "python {backtest_script}"
    thresholds:
      min_sharpe: 1.0
      max_drawdown: 0.2
      min_trades: 10
      max_oos_is_gap_pct: 50
    code_budget:
      max_file_loc: 500
      ignore_file: .codebudgetignore
    safety:
      paper_only: true
      live_enable_flag_path: .spotcat/LIVE_ENABLED
      global_kill_switch: "~/.spotcat/GLOBAL_LIVE_ENABLE"
      idempotency_key_format: "{{strategy_id}}_{{signal_timestamp}}_{{side}}"
    """)


def _make_pilot_project(tmp_path, all_tests_pass: bool):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")

    project_root = tmp_path / "project"
    project_root.mkdir()

    outcome = "passed" if all_tests_pass else "failed"
    test_script = project_root / "run_tests.py"
    report_path = project_root / ".spotcat" / "last-test-result.json"
    test_script.write_text(
        "import json, pathlib\n"
        f"pathlib.Path({str(report_path)!r}).parent.mkdir(parents=True, exist_ok=True)\n"
        f"report = {{'tests': ["
        f"{{'nodeid': 'test_x.py::test_position_limit_enforced', 'outcome': {outcome!r}}},"
        f"{{'nodeid': 'test_x.py::test_duplicate_signal_not_double_ordered', 'outcome': {outcome!r}}},"
        f"{{'nodeid': 'test_x.py::test_live_trading_requires_dual_kill_switch', 'outcome': {outcome!r}}},"
        f"]}}\n"
        f"pathlib.Path({str(report_path)!r}).write_text(json.dumps(report))\n"
    )

    from spotcat_gates.data_files import hash_data_files, resolve_data_files
    cfg_for_hash = {
        "paths": {"data_root": str(data_root), "data_format": "csv",
                   "expected_date_range": {"start": "2024-01-01", "end": "2024-01-01"}},
    }
    data_hash = hash_data_files(resolve_data_files(cfg_for_hash), data_root)

    backtest_script = project_root / "run_backtest.py"
    result_path = project_root / ".spotcat" / "last-backtest-result.json"
    backtest_result = {
        "sharpe_ratio": 1.5, "max_drawdown": 0.1, "win_rate": 0.55, "trade_count": 40,
        "profit_factor": 1.3, "in_sample_sharpe": 1.6, "out_sample_sharpe": 1.4,
        "lookahead_check": "not_run", "data_hash": data_hash, "generated_at": "2026-08-26T00:00:00Z",
    }
    backtest_script.write_text(
        "import json, pathlib\n"
        f"pathlib.Path({str(result_path)!r}).parent.mkdir(parents=True, exist_ok=True)\n"
        f"pathlib.Path({str(result_path)!r}).write_text(json.dumps({backtest_result!r}))\n"
    )

    # 用 as_posix() 避免 Windows 路径里的反斜杠被 YAML 双引号字符串当作转义序列解析。
    config_yaml = CONFIG_YAML.format(
        data_root=data_root.as_posix(),
        test_script=test_script.as_posix(),
        backtest_script=backtest_script.as_posix(),
    )
    config_path = project_root / ".spotcat" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_yaml)
    return project_root, config_path


def test_run_all_gates_pass(tmp_path):
    project_root, config_path = _make_pilot_project(tmp_path, all_tests_pass=True)
    from spotcat_gates.config import load_config
    config = load_config(config_path)

    results, overall = run_all_gates(config, project_root)
    assert all(r.status == "PASS" for r in results if r.gate != "lookahead-replay")
    # lookahead-replay is ERROR here because replay_check_dates isn't configured in this fixture —
    # that's an expected, visible ERROR, not a silent pass. Per the documented overall_status
    # priority (FAIL > ERROR > PASS), that visible ERROR correctly makes overall == "ERROR"
    # rather than silently reporting PASS.
    lookahead = next(r for r in results if r.gate == "lookahead-replay")
    assert lookahead.status == "ERROR"
    assert overall == "ERROR"


def test_run_all_gates_fail_on_behavioral_test(tmp_path):
    project_root, config_path = _make_pilot_project(tmp_path, all_tests_pass=False)
    from spotcat_gates.config import load_config
    config = load_config(config_path)

    results, overall = run_all_gates(config, project_root)
    assert overall == "FAIL"
    position_limit = next(r for r in results if r.gate == "position-limit")
    assert position_limit.status == "FAIL"


def test_main_writes_output_and_returns_nonzero_on_fail(tmp_path, monkeypatch, capsys):
    project_root, config_path = _make_pilot_project(tmp_path, all_tests_pass=False)
    from spotcat_gates.gate_runner import main

    exit_code = main(["--config", str(config_path), "--run-id", "test-run-1"])
    assert exit_code != 0

    out_path = project_root / ".spotcat" / "runs" / "test-run-1" / "gate-output.json"
    assert out_path.is_file()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "FAIL"
    assert payload["run_id"] == "test-run-1"


# --- amendment: credentials-gate file listing must exclude common non-source directories ---

def test_is_excluded_true_for_each_excluded_dir_name():
    project_root = Path("/proj")
    for dirname in (".venv", "venv", "__pycache__", ".git", "node_modules", ".spotcat"):
        p = project_root / dirname / "nested" / "file.py"
        assert _is_excluded(p, project_root), f"{dirname} should be excluded"


def test_is_excluded_false_for_normal_source_file():
    project_root = Path("/proj")
    p = project_root / "strategies" / "my_strategy.py"
    assert not _is_excluded(p, project_root)


def test_run_all_gates_credentials_scan_excludes_venv_and_spotcat_dirs(tmp_path):
    project_root, config_path = _make_pilot_project(tmp_path, all_tests_pass=True)
    from spotcat_gates.config import load_config
    config = load_config(config_path)

    # Before adding any excluded-dir files: only run_tests.py and run_backtest.py are scannable.
    baseline_results, _ = run_all_gates(config, project_root)
    baseline_credentials = next(r for r in baseline_results if r.gate == "credentials")
    baseline_count = baseline_credentials.details["scanned_files"]

    # Plant .py files inside directories that must be excluded from the credentials scan.
    for dirname in (".venv", "venv", "__pycache__", ".git", "node_modules", ".spotcat"):
        d = project_root / dirname / "sub"
        d.mkdir(parents=True, exist_ok=True)
        fake_key = "sk_live_" + "FIXTURE0000000000000EXAMPLE"
        (d / "vendored.py").write_text("api_key = '" + fake_key + "'\n")

    results, _overall = run_all_gates(config, project_root)
    credentials = next(r for r in results if r.gate == "credentials")

    # scanned_files count must be unchanged — none of the planted files were scanned.
    assert credentials.details["scanned_files"] == baseline_count
    # And since the only hardcoded secret is inside excluded dirs, the gate must still PASS.
    # (overall_status is not asserted here: lookahead-replay is independently ERROR in this
    # fixture because replay_check_dates isn't configured — see test_run_all_gates_pass. That's
    # orthogonal to what this test verifies: the credentials scan's directory exclusion.)
    assert credentials.status == "PASS"
