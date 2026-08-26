from spotcat_gates.gates.behavioral import check_idempotency, check_kill_switch, check_position_limit

PASSING_REPORT = {
    "tests": [
        {"nodeid": "tests/test_risk.py::test_position_limit_enforced", "outcome": "passed"},
        {"nodeid": "tests/test_risk.py::test_duplicate_signal_not_double_ordered", "outcome": "passed"},
        {"nodeid": "tests/test_risk.py::test_live_trading_requires_dual_kill_switch", "outcome": "passed"},
    ]
}

FAILING_REPORT = {
    "tests": [
        {"nodeid": "tests/test_risk.py::test_position_limit_enforced", "outcome": "failed"},
    ]
}

EMPTY_REPORT = {"tests": []}


def test_position_limit_pass():
    r = check_position_limit(PASSING_REPORT)
    assert r.status == "PASS"
    assert r.gate == "position-limit"
    assert r.evidence_tier == "A"


def test_position_limit_fail_when_test_fails():
    r = check_position_limit(FAILING_REPORT)
    assert r.status == "FAIL"
    assert "failed" in r.details["reason"]


def test_position_limit_fail_when_test_missing():
    r = check_position_limit(EMPTY_REPORT)
    assert r.status == "FAIL"
    assert "not found" in r.details["reason"]


def test_idempotency_pass():
    assert check_idempotency(PASSING_REPORT).status == "PASS"


def test_kill_switch_pass():
    assert check_kill_switch(PASSING_REPORT).status == "PASS"
