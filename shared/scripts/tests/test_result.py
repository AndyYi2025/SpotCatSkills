import pytest

from spotcat_gates.result import GateResult


def test_valid_result_to_dict():
    r = GateResult(gate="credentials", status="PASS", evidence_tier="A", details={"scanned_files": 3})
    assert r.to_dict() == {
        "gate": "credentials",
        "status": "PASS",
        "evidence_tier": "A",
        "details": {"scanned_files": 3},
    }


def test_invalid_status_rejected():
    with pytest.raises(ValueError, match="status"):
        GateResult(gate="credentials", status="MAYBE", evidence_tier="A", details={})


def test_invalid_evidence_tier_rejected():
    with pytest.raises(ValueError, match="evidence_tier"):
        GateResult(gate="credentials", status="PASS", evidence_tier="Z", details={})
