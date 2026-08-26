from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spotcat_gates.capture import new_run_id, write_gate_output
from spotcat_gates.config import ConfigError, load_config
from spotcat_gates.gates.backtest_metrics import check_backtest_metrics
from spotcat_gates.gates.behavioral import check_idempotency, check_kill_switch, check_position_limit
from spotcat_gates.gates.credentials import check_credentials
from spotcat_gates.gates.date_gap import check_date_gap
from spotcat_gates.gates.lookahead_replay import check_lookahead_replay
from spotcat_gates.result import GateResult
from spotcat_gates.test_report import TestReportError, run_test_command

# 常见非源码目录：第三方/虚拟环境依赖、VCS 内部数据、本工具自身运行时产物。
# 凭据扫描不应遍历这些目录 —— 既慢，又容易在项目作者未编写的代码上产生误报。
_EXCLUDED_DIR_NAMES = {".venv", "venv", "__pycache__", ".git", "node_modules", ".spotcat"}


def _is_excluded(path: Path, project_root: Path) -> bool:
    """判断 path（相对 project_root）是否落在需要从凭据扫描中排除的目录下。"""
    relparts = Path(path).relative_to(project_root).parts
    return any(part in _EXCLUDED_DIR_NAMES for part in relparts)


def run_all_gates(config: dict, project_root: Path) -> tuple[list[GateResult], str]:
    project_root = Path(project_root)
    results: list[GateResult] = []

    strategy_files = [
        f for f in project_root.rglob("*.py") if not _is_excluded(f, project_root)
    ]
    results.append(check_credentials(strategy_files))

    try:
        report = run_test_command(config, project_root)
    except TestReportError as e:
        err = GateResult(gate="behavioral-tests", status="ERROR", evidence_tier="A", details={"reason": str(e)})
        results.extend([err, err, err])
        report = None

    if report is not None:
        results.append(check_position_limit(report))
        results.append(check_idempotency(report))
        results.append(check_kill_switch(report))

    date_gap_result = check_date_gap(config)
    results.append(date_gap_result)

    if date_gap_result.status == "PASS":
        results.append(check_backtest_metrics(config, project_root))
        results.append(check_lookahead_replay(config, project_root))
    else:
        skipped_detail = {"reason": "skipped: date-gap gate failed"}
        results.append(GateResult(gate="backtest-metrics", status="ERROR", evidence_tier="A", details=skipped_detail))
        results.append(GateResult(gate="lookahead-replay", status="ERROR", evidence_tier="B", details=skipped_detail))

    if any(r.status == "FAIL" for r in results):
        overall = "FAIL"
    elif any(r.status == "ERROR" for r in results):
        overall = "ERROR"
    else:
        overall = "PASS"

    return results, overall


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gate-runner")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return 2

    project_root = Path(args.config).resolve().parent.parent  # .spotcat/config.yml -> project root
    run_id = args.run_id or new_run_id()

    results, overall = run_all_gates(config, project_root)
    out_path = write_gate_output(project_root, run_id, results, overall)
    print(f"gate-runner: overall={overall} output={out_path}")

    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
