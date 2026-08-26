from __future__ import annotations

from dataclasses import dataclass, field

_VALID_STATUS = {"PASS", "FAIL", "ERROR"}
_VALID_TIER = {"A", "B", "C"}


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: str
    evidence_tier: str
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in _VALID_STATUS:
            raise ValueError(f"status must be one of {_VALID_STATUS}, got {self.status!r}")
        if self.evidence_tier not in _VALID_TIER:
            raise ValueError(f"evidence_tier must be one of {_VALID_TIER}, got {self.evidence_tier!r}")

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "status": self.status,
            "evidence_tier": self.evidence_tier,
            "details": self.details,
        }
