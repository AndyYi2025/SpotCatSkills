from __future__ import annotations

from spotcat_gates.result import GateResult
from spotcat_gates.test_report import check_named_test

REQUIRED_TEST_NAMES = {
    "position-limit": "test_position_limit_enforced",
    "idempotency": "test_duplicate_signal_not_double_ordered",
    "kill-switch": "test_live_trading_requires_dual_kill_switch",
}


def _check(gate_name: str, report: dict) -> GateResult:
    test_name = REQUIRED_TEST_NAMES[gate_name]
    found, passed = check_named_test(report, test_name)
    if not found:
        return GateResult(
            gate=gate_name, status="FAIL", evidence_tier="A",
            details={"reason": f"required test not found: {test_name}", "required_test": test_name},
        )
    if not passed:
        return GateResult(
            gate=gate_name, status="FAIL", evidence_tier="A",
            details={"reason": f"required test failed: {test_name}", "required_test": test_name},
        )
    return GateResult(
        gate=gate_name, status="PASS", evidence_tier="A",
        details={"required_test": test_name},
    )


def check_position_limit(report: dict) -> GateResult:
    return _check("position-limit", report)


def check_idempotency(report: dict) -> GateResult:
    return _check("idempotency", report)


def check_kill_switch(report: dict) -> GateResult:
    return _check("kill-switch", report)
