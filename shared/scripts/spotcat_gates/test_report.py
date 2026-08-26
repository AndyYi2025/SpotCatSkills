from __future__ import annotations

import json
import subprocess
from pathlib import Path


class TestReportError(Exception):
    pass


def run_test_command(
    config: dict, project_root: Path, report_relpath: str = ".spotcat/last-test-result.json"
) -> dict:
    cmd = config["commands"]["test"]
    try:
        subprocess.run(cmd, shell=True, cwd=project_root, timeout=1800)
    except (subprocess.SubprocessError, OSError) as e:
        raise TestReportError(f"test command failed to run: {e}") from e

    report_path = Path(project_root) / report_relpath
    if not report_path.is_file():
        raise TestReportError(f"report file not found: {report_path}")

    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TestReportError(f"report file is not valid JSON: {e}") from e


def check_named_test(report: dict, test_name_suffix: str) -> tuple[bool, bool]:
    for t in report.get("tests", []):
        if t.get("nodeid", "").endswith(test_name_suffix):
            return True, t.get("outcome") == "passed"
    return False, False
