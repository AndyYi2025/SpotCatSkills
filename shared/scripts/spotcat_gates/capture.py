from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from spotcat_gates.result import GateResult


def new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{ts}-{secrets.token_hex(4)}"


def write_gate_output(
    project_root: Path, run_id: str, results: list[GateResult], overall_status: str
) -> Path:
    if any(c in run_id for c in ("/", "\\")) or ".." in run_id:
        raise ValueError(f"run_id must not contain path separators or '..': {run_id!r}")

    run_dir = Path(project_root) / ".spotcat" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "gate-output.json"

    payload = {
        "run_id": run_id,
        "overall_status": overall_status,
        "gates": [r.to_dict() for r in results],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path
