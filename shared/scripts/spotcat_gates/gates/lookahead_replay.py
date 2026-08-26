from __future__ import annotations

import json
import subprocess
from pathlib import Path

from spotcat_gates.result import GateResult


def _run_replay(cmd_template: str, cutoff: str, project_root: Path) -> list[dict]:
    cmd = cmd_template.format(cutoff=cutoff)
    proc = subprocess.run(cmd, shell=True, cwd=project_root, capture_output=True, text=True, timeout=600)
    return json.loads(proc.stdout)


def check_lookahead_replay(config: dict, project_root: Path) -> GateResult:
    dates = config.get("paths", {}).get("replay_check_dates")
    if not dates:
        return GateResult(
            gate="lookahead-replay", status="ERROR", evidence_tier="B",
            details={"reason": "paths.replay_check_dates not configured — gate not wired up"},
        )

    cmd_template = config.get("commands", {}).get("lookahead_replay")
    if not cmd_template:
        return GateResult(
            gate="lookahead-replay", status="ERROR", evidence_tier="B",
            details={"reason": "commands.lookahead_replay not configured — gate not wired up"},
        )

    t, t_plus_k = dates["t"], dates["t_plus_k"]
    try:
        run_t = _run_replay(cmd_template, t, project_root)
        run_t_plus_k = _run_replay(cmd_template, t_plus_k, project_root)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as e:
        return GateResult(
            gate="lookahead-replay", status="ERROR", evidence_tier="B",
            details={"reason": f"replay command failed: {e}"},
        )

    cutoff_t_iso = t + "T23:59:59"
    prefix_from_later_run = [s for s in run_t_plus_k if s["timestamp"] <= cutoff_t_iso]

    if run_t != prefix_from_later_run:
        for a, b in zip(run_t, prefix_from_later_run):
            if a != b:
                return GateResult(
                    gate="lookahead-replay", status="FAIL", evidence_tier="B",
                    details={"reason": f"signal at {a['timestamp']} changed between cutoffs: {a} != {b}"},
                )
        return GateResult(
            gate="lookahead-replay", status="FAIL", evidence_tier="B",
            details={"reason": "signal series length differs between cutoff runs"},
        )

    return GateResult(
        gate="lookahead-replay", status="PASS", evidence_tier="B",
        details={"compared_points": len(run_t)},
    )
