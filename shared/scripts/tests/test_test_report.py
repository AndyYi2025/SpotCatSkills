import json
import textwrap

import pytest

from spotcat_gates.test_report import TestReportError, check_named_test, run_test_command

REPORT = {
    "tests": [
        {"nodeid": "tests/test_risk.py::test_position_limit_enforced", "outcome": "passed"},
        {"nodeid": "tests/test_risk.py::test_duplicate_signal_not_double_ordered", "outcome": "failed"},
    ]
}


def test_check_named_test_found_and_passed():
    found, passed = check_named_test(REPORT, "test_position_limit_enforced")
    assert (found, passed) == (True, True)


def test_check_named_test_found_and_failed():
    found, passed = check_named_test(REPORT, "test_duplicate_signal_not_double_ordered")
    assert (found, passed) == (True, False)


def test_check_named_test_not_found():
    found, passed = check_named_test(REPORT, "test_live_trading_requires_dual_kill_switch")
    assert (found, passed) == (False, False)


def test_run_test_command_success(tmp_path):
    report_path = tmp_path / ".spotcat" / "last-test-result.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps(REPORT), encoding="utf-8")

    # command just needs to exit 0; report already on disk for this fixture
    config = {"commands": {"test": "python -c \"pass\""}}
    result = run_test_command(config, tmp_path, report_relpath=".spotcat/last-test-result.json")
    assert result == REPORT


def test_run_test_command_missing_report_raises(tmp_path):
    config = {"commands": {"test": "python -c \"pass\""}}
    with pytest.raises(TestReportError, match="report file not found"):
        run_test_command(config, tmp_path, report_relpath=".spotcat/last-test-result.json")


def test_run_test_command_nonzero_exit_still_reads_report(tmp_path):
    # pytest itself exits non-zero when tests fail — that's expected, not a gate ERROR.
    report_path = tmp_path / ".spotcat" / "last-test-result.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps(REPORT), encoding="utf-8")
    config = {"commands": {"test": "python -c \"import sys; sys.exit(1)\""}}
    result = run_test_command(config, tmp_path, report_relpath=".spotcat/last-test-result.json")
    assert result == REPORT


def test_check_named_test_no_literal_suffix_false_positive():
    # Test that a nodeid ending with the suffix string doesn't falsely match
    # e.g., "test_final_test_position_limit_enforced" should not match "test_position_limit_enforced"
    report = {
        "tests": [
            {"nodeid": "tests/test_x.py::test_final_test_position_limit_enforced", "outcome": "passed"},
        ]
    }
    found, passed = check_named_test(report, "test_position_limit_enforced")
    assert (found, passed) == (False, False)


def test_check_named_test_multiple_same_name_checks_all():
    # Test that when the same test name appears in multiple files,
    # we check ALL of them and fail if ANY fails
    report = {
        "tests": [
            {"nodeid": "tests/test_unit.py::test_position_limit_enforced", "outcome": "passed"},
            {"nodeid": "tests/test_integration.py::test_position_limit_enforced", "outcome": "failed"},
        ]
    }
    found, passed = check_named_test(report, "test_position_limit_enforced")
    # Should find both, but fail because not ALL are passed
    assert (found, passed) == (True, False)
