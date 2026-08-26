import hashlib
from pathlib import Path

import pytest

from spotcat_gates.data_files import DataFilesError, hash_data_files, missing_dates, resolve_data_files


def _config(data_root, start, end):
    return {
        "paths": {
            "data_root": str(data_root),
            "data_format": "csv",
            "expected_date_range": {"start": start, "end": end},
        }
    }


def test_resolve_data_files_filters_by_date_range(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "2024-01-02.csv").write_text("b")
    (tmp_path / "2023-12-31.csv").write_text("c")  # outside range
    cfg = _config(tmp_path, "2024-01-01", "2024-01-02")
    files = resolve_data_files(cfg)
    assert sorted(f.name for f in files) == ["2024-01-01.csv", "2024-01-02.csv"]


def test_missing_dates_reports_gap(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "2024-01-03.csv").write_text("c")
    cfg = _config(tmp_path, "2024-01-01", "2024-01-03")
    files = resolve_data_files(cfg)
    assert missing_dates(cfg, files) == ["2024-01-02"]


def test_missing_dates_empty_when_complete(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "2024-01-02.csv").write_text("b")
    cfg = _config(tmp_path, "2024-01-01", "2024-01-02")
    files = resolve_data_files(cfg)
    assert missing_dates(cfg, files) == []


def test_hash_data_files_deterministic_and_content_sensitive(tmp_path):
    f1 = tmp_path / "2024-01-01.csv"
    f1.write_text("a")
    f2 = tmp_path / "2024-01-02.csv"
    f2.write_text("b")

    h1 = hash_data_files([f1, f2], tmp_path)
    h2 = hash_data_files([f2, f1], tmp_path)  # order must not matter
    assert h1 == h2

    f1.write_text("changed")
    h3 = hash_data_files([f1, f2], tmp_path)
    assert h3 != h1


def test_resolve_data_files_skips_invalid_date_shapes(tmp_path):
    """Files with syntactically valid but semantically invalid dates should be skipped."""
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "report_2024-13-40_draft.csv").write_text("b")  # month 13, day 40
    (tmp_path / "2024-01-02.csv").write_text("c")
    cfg = _config(tmp_path, "2024-01-01", "2024-01-02")
    files = resolve_data_files(cfg)
    # Should not crash, should skip the invalid date file
    assert sorted(f.name for f in files) == ["2024-01-01.csv", "2024-01-02.csv"]


def test_missing_dates_skips_invalid_date_shapes(tmp_path):
    """Files with invalid dates should not cause missing_dates to crash."""
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "report_2024-13-40_draft.csv").write_text("b")  # invalid date
    (tmp_path / "2024-01-03.csv").write_text("c")
    cfg = _config(tmp_path, "2024-01-01", "2024-01-03")
    files = resolve_data_files(cfg)
    # Should not crash, should correctly report 2024-01-02 as missing
    assert missing_dates(cfg, files) == ["2024-01-02"]


def test_resolve_data_files_returns_empty_for_nonexistent_directory(tmp_path):
    """Non-existent data_root should return empty list, not crash."""
    nonexistent = tmp_path / "does_not_exist"
    cfg = _config(nonexistent, "2024-01-01", "2024-01-02")
    files = resolve_data_files(cfg)
    assert files == []


def test_resolve_data_files_with_end_date_auto(tmp_path):
    """expected_date_range.end == 'auto' should use today's date."""
    import datetime
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    (tmp_path / f"{yesterday.isoformat()}.csv").write_text("a")
    (tmp_path / f"{today.isoformat()}.csv").write_text("b")
    tomorrow = today + datetime.timedelta(days=1)
    (tmp_path / f"{tomorrow.isoformat()}.csv").write_text("c")  # outside range

    cfg = {
        "paths": {
            "data_root": str(tmp_path),
            "data_format": "csv",
            "expected_date_range": {"start": yesterday.isoformat(), "end": "auto"},
        }
    }
    files = resolve_data_files(cfg)
    # Should include yesterday and today, but not tomorrow
    names = sorted(f.name for f in files)
    assert names == [f"{yesterday.isoformat()}.csv", f"{today.isoformat()}.csv"]


def test_resolve_data_files_invalid_start_date_raises_error(tmp_path):
    """Invalid date string in expected_date_range.start should raise DataFilesError."""
    (tmp_path / "2024-01-01.csv").write_text("a")
    cfg = _config(tmp_path, "not-a-date", "2024-01-02")
    with pytest.raises(DataFilesError):
        resolve_data_files(cfg)


def test_resolve_data_files_invalid_end_date_raises_error(tmp_path):
    """Invalid date string in expected_date_range.end should raise DataFilesError."""
    (tmp_path / "2024-01-01.csv").write_text("a")
    cfg = _config(tmp_path, "2024-01-01", "2024-13-01")
    with pytest.raises(DataFilesError):
        resolve_data_files(cfg)
