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
    """Check for tests matching the given suffix by anchoring to the last nodeid segment.

    Args:
        report: pytest-json-report dict with "tests" list
        test_name_suffix: test name to match (compared to last segment of nodeid after ::)

    Returns:
        (found, passed) where:
        - found: True if at least one test matches
        - passed: True only if ALL matching tests have outcome == "passed"
    """
    matching_tests = []
    for t in report.get("tests", []):
        nodeid = t.get("nodeid", "")
        # Split by :: and check if the last segment exactly matches
        if "::" in nodeid:
            last_segment = nodeid.split("::")[-1]
        else:
            last_segment = nodeid

        if last_segment == test_name_suffix:
            matching_tests.append(t)

    if not matching_tests:
        return False, False

    # All matching tests must have outcome == "passed"
    all_passed = all(t.get("outcome") == "passed" for t in matching_tests)
    return True, all_passed
