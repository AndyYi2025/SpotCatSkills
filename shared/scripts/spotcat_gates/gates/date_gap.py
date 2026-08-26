from __future__ import annotations

from spotcat_gates.data_files import missing_dates, resolve_data_files
from spotcat_gates.result import GateResult


def check_date_gap(config: dict) -> GateResult:
    files = resolve_data_files(config)
    gaps = missing_dates(config, files)
    if gaps:
        return GateResult(
            gate="date-gap", status="FAIL", evidence_tier="A",
            details={"missing_dates": gaps, "files_found": len(files)},
        )
    return GateResult(
        gate="date-gap", status="PASS", evidence_tier="A",
        details={"files_found": len(files)},
    )
