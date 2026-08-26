import pytest

from spotcat_gates.gates.date_gap import check_date_gap


def _config(data_root, start, end):
    return {
        "paths": {
            "data_root": str(data_root),
            "data_format": "csv",
            "expected_date_range": {"start": start, "end": end},
        }
    }


def test_date_gap_pass_when_complete(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "2024-01-02.csv").write_text("b")
    r = check_date_gap(_config(tmp_path, "2024-01-01", "2024-01-02"))
    assert r.status == "PASS"


def test_date_gap_fail_when_missing(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    r = check_date_gap(_config(tmp_path, "2024-01-01", "2024-01-03"))
    assert r.status == "FAIL"
    assert r.details["missing_dates"] == ["2024-01-02", "2024-01-03"]


def test_date_gap_error_on_invalid_start_date(tmp_path):
    """Invalid date string in config should return ERROR status, not crash."""
    (tmp_path / "2024-01-01.csv").write_text("a")
    r = check_date_gap(_config(tmp_path, "not-a-date", "2024-01-02"))
    assert r.status == "ERROR"
    assert "reason" in r.details


def test_date_gap_error_on_invalid_end_date(tmp_path):
    """Invalid end date in config should return ERROR status, not crash."""
    (tmp_path / "2024-01-01.csv").write_text("a")
    r = check_date_gap(_config(tmp_path, "2024-01-01", "2024-13-01"))
    assert r.status == "ERROR"
    assert "reason" in r.details


def test_date_gap_error_when_data_root_not_a_directory(tmp_path):
    """A nonexistent data_root must be ERROR (tool couldn't find the data), not FAIL
    (which would conflate it with 'data directory exists but has real gaps')."""
    nonexistent = tmp_path / "does_not_exist"
    r = check_date_gap(_config(nonexistent, "2024-01-01", "2024-01-02"))
    assert r.status == "ERROR"
    assert "reason" in r.details
