import hashlib

from spotcat_gates.data_files import hash_data_files, missing_dates, resolve_data_files


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

    h1 = hash_data_files([f1, f2])
    h2 = hash_data_files([f2, f1])  # order must not matter
    assert h1 == h2

    f1.write_text("changed")
    h3 = hash_data_files([f1, f2])
    assert h3 != h1
