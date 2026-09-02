from spotcat_gates.gates.duplicate_symbols import check_duplicate_symbols


def test_pass_when_no_duplicate_names(tmp_path):
    (tmp_path / "a.py").write_text("def load_data():\n    pass\n")
    (tmp_path / "b.py").write_text("def save_data():\n    pass\n")
    r = check_duplicate_symbols(tmp_path, [tmp_path / "a.py", tmp_path / "b.py"])
    assert r.status == "PASS"
    assert r.details["scanned_files"] == 2


def test_fail_when_same_function_name_in_two_files(tmp_path):
    (tmp_path / "a.py").write_text("def calculate_signal():\n    pass\n")
    (tmp_path / "b.py").write_text("def calculate_signal():\n    pass\n")
    r = check_duplicate_symbols(tmp_path, [tmp_path / "a.py", tmp_path / "b.py"])
    assert r.status == "FAIL"
    assert r.details["duplicates"] == {"calculate_signal": ["a.py", "b.py"]}


def test_fail_when_same_class_name_in_two_files(tmp_path):
    (tmp_path / "a.py").write_text("class RiskConfig:\n    pass\n")
    (tmp_path / "b.py").write_text("class RiskConfig:\n    pass\n")
    r = check_duplicate_symbols(tmp_path, [tmp_path / "a.py", tmp_path / "b.py"])
    assert r.status == "FAIL"
    assert r.details["duplicates"] == {"RiskConfig": ["a.py", "b.py"]}


def test_repeated_name_within_single_file_is_not_a_duplicate(tmp_path):
    # Same name twice in one file (e.g. a redefinition) is a single-file concern, not
    # cross-file duplication -- this gate only flags reimplementation across files.
    (tmp_path / "a.py").write_text("def f():\n    pass\ndef f():\n    pass\n")
    r = check_duplicate_symbols(tmp_path, [tmp_path / "a.py"])
    assert r.status == "PASS"


def test_test_files_are_excluded_from_duplicate_check(tmp_path):
    (tmp_path / "test_a.py").write_text("def test_basic():\n    pass\n")
    (tmp_path / "test_b.py").write_text("def test_basic():\n    pass\n")
    r = check_duplicate_symbols(tmp_path, [tmp_path / "test_a.py", tmp_path / "test_b.py"])
    assert r.status == "PASS"
    assert r.details["scanned_files"] == 0


def test_files_under_tests_dir_are_excluded(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "helpers.py").write_text("def build_fixture():\n    pass\n")
    (tmp_path / "helpers.py").write_text("def build_fixture():\n    pass\n")
    r = check_duplicate_symbols(tmp_path, [tests_dir / "helpers.py", tmp_path / "helpers.py"])
    assert r.status == "PASS"
    assert r.details["scanned_files"] == 1


def test_unparseable_file_is_reported_not_silently_dropped(tmp_path):
    (tmp_path / "broken.py").write_text("def f(:\n    pass\n")  # syntax error
    (tmp_path / "ok.py").write_text("def g():\n    pass\n")
    r = check_duplicate_symbols(tmp_path, [tmp_path / "broken.py", tmp_path / "ok.py"])
    assert r.status == "PASS"
    assert r.details["unparseable_files"] == ["broken.py"]
    assert r.details["scanned_files"] == 1
