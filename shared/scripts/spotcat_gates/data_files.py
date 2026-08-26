from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _parse_range(config: dict) -> tuple[date, date]:
    rng = config["paths"]["expected_date_range"]
    start = date.fromisoformat(rng["start"])
    end_raw = rng["end"]
    end = date.today() if end_raw == "auto" else date.fromisoformat(end_raw)
    return start, end


def resolve_data_files(config: dict) -> list[Path]:
    start, end = _parse_range(config)
    root = Path(config["paths"]["data_root"])
    if not root.is_dir():
        return []
    out = []
    for f in root.iterdir():
        if not f.is_file():
            continue
        m = _DATE_RE.search(f.name)
        if not m:
            continue
        d = date.fromisoformat(m.group(1))
        if start <= d <= end:
            out.append(f)
    return sorted(out)


def missing_dates(config: dict, files: list[Path]) -> list[str]:
    start, end = _parse_range(config)
    present = set()
    for f in files:
        m = _DATE_RE.search(f.name)
        if m:
            present.add(m.group(1))

    missing = []
    d = start
    while d <= end:
        iso = d.isoformat()
        if iso not in present:
            missing.append(iso)
        d += timedelta(days=1)
    return missing


def hash_data_files(files: list[Path]) -> str:
    lines = []
    for f in sorted(files, key=lambda p: p.name):
        content_hash = hashlib.sha256(Path(f).read_bytes()).hexdigest()
        lines.append(f"{Path(f).name}:{content_hash}")
    combined = "\n".join(sorted(lines))
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
