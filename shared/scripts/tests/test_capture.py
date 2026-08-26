import json

import pytest

from spotcat_gates.capture import new_run_id, write_gate_output
from spotcat_gates.result import GateResult


def test_write_gate_output_creates_file(tmp_path):
    results = [GateResult(gate="credentials", status="PASS", evidence_tier="A", details={})]
    out = write_gate_output(tmp_path, "20260826-abcd12", results, overall_status="PASS")
    assert out == tmp_path / ".spotcat" / "runs" / "20260826-abcd12" / "gate-output.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["run_id"] == "20260826-abcd12"
    assert payload["overall_status"] == "PASS"
    assert payload["gates"] == [
        {"gate": "credentials", "status": "PASS", "evidence_tier": "A", "details": {}}
    ]


def test_write_gate_output_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="run_id"):
        write_gate_output(tmp_path, "../escape", [], overall_status="PASS")


def test_new_run_id_format():
    rid = new_run_id()
    assert len(rid.split("-")) == 2
    date_part, hex_part = rid.split("-")
    assert len(date_part) == 15  # YYYYMMDD-HHMMSS minus the dash, see impl
    assert len(hex_part) == 8
