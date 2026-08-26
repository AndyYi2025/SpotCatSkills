from spotcat_gates.gates.credentials import check_credentials


def test_credentials_pass_on_clean_file(tmp_path):
    f = tmp_path / "strategy.py"
    f.write_text("api_key = os.environ['BROKER_API_KEY']\n")
    r = check_credentials([f])
    assert r.status == "PASS"
    assert r.details["scanned_files"] == 1


def test_credentials_fail_on_hardcoded_key(tmp_path):
    f = tmp_path / "strategy.py"
    fake_key = "sk_live_" + "FIXTURE0000000000000EXAMPLE"
    f.write_text(f'api_key = "{fake_key}"\n')
    r = check_credentials([f])
    assert r.status == "FAIL"
    assert str(f) in r.details["findings"][0]["file"]


def test_credentials_fail_on_aws_style_key(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"\n')
    r = check_credentials([f])
    assert r.status == "FAIL"


def test_credentials_error_on_unreadable_file(tmp_path):
    missing = tmp_path / "does-not-exist.py"
    r = check_credentials([missing])
    assert r.status == "ERROR"
