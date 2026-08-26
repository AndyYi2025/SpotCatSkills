from __future__ import annotations

import re
from pathlib import Path

from spotcat_gates.result import GateResult

# Deliberately simple, self-contained patterns — not a full entropy scanner. Extend this list
# rather than reaching for an external binary dependency (spec §2.2 "或等价正则/熵检测").
_PATTERNS = [
    ("stripe-like-secret", re.compile(r"sk_live_[A-Za-z0-9]{20,}")),
    ("aws-access-key-id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic-assigned-secret", re.compile(
        r"(?i)(api_key|secret|password|token)\s*=\s*[\"'][A-Za-z0-9/+_\-]{16,}[\"']"
    )),
]


def check_credentials(paths: list[Path]) -> GateResult:
    findings = []
    for p in paths:
        p = Path(p)
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (FileNotFoundError, UnicodeDecodeError, OSError) as e:
            return GateResult(
                gate="credentials", status="ERROR", evidence_tier="A",
                details={"reason": f"could not read {p}: {e}"},
            )
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in _PATTERNS:
                if pattern.search(line):
                    findings.append({"file": str(p), "line": line_no, "pattern": name})

    if findings:
        return GateResult(
            gate="credentials", status="FAIL", evidence_tier="A",
            details={"findings": findings, "scanned_files": len(paths)},
        )
    return GateResult(
        gate="credentials", status="PASS", evidence_tier="A",
        details={"scanned_files": len(paths)},
    )
