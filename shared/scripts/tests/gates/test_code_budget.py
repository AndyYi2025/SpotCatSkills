import pytest

from spotcat_gates.gates.code_budget import check_code_budget


def _config(max_file_loc=500, ignore_file=".codebudgetignore"):
    return {"code_budget": {"max_file_loc": max_file_loc, "ignore_file": ignore_file}}


def _write_lines(path, n):
    path.write_text("\n".join(f"x = {i}" for i in range(n)) + "\n")


def test_code_budget_pass_when_all_files_within_budget(tmp_path):
    f = tmp_path / "strategy.py"
    _write_lines(f, 10)
    r = check_code_budget(_config(max_file_loc=500), tmp_path, [f])
    assert r.status == "PASS"
    assert r.details["scanned_files"] == 1


def test_code_budget_fail_when_file_exceeds_budget(tmp_path):
    f = tmp_path / "big_strategy.py"
    _write_lines(f, 20)
    r = check_code_budget(_config(max_file_loc=10), tmp_path, [f])
    assert r.status == "FAIL"
    assert r.details["violations"] == [{"file": "big_strategy.py", "loc": 20, "max_file_loc": 10}]


def test_code_budget_ignores_files_matched_by_ignore_file(tmp_path):
    f = tmp_path / "legacy_pb2.py"
    _write_lines(f, 999)
    (tmp_path / ".codebudgetignore").write_text("*_pb2.py\n")
    r = check_code_budget(_config(max_file_loc=10), tmp_path, [f])
    assert r.status == "PASS"
    assert r.details["scanned_files"] == 0


def test_code_budget_ignore_file_comments_and_blank_lines_are_skipped(tmp_path):
    f = tmp_path / "big.py"
    _write_lines(f, 20)
    (tmp_path / ".codebudgetignore").write_text("# comment\n\nother_pattern.py\n")
    r = check_code_budget(_config(max_file_loc=10), tmp_path, [f])
    assert r.status == "FAIL"


def test_code_budget_missing_ignore_file_is_not_an_error(tmp_path):
    f = tmp_path / "strategy.py"
    _write_lines(f, 5)
    r = check_code_budget(_config(max_file_loc=500, ignore_file=".codebudgetignore"), tmp_path, [f])
    assert r.status == "PASS"


def test_code_budget_error_when_file_unreadable(tmp_path):
    f = tmp_path / "vanished.py"
    _write_lines(f, 5)
    f.unlink()
    r = check_code_budget(_config(), tmp_path, [f])
    assert r.status == "ERROR"
    assert "reason" in r.details
