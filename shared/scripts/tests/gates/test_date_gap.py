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
